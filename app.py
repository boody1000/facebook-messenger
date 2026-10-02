import torch
from flask import Flask, jsonify, render_template, request
from transformers import AutoModelForCausalLM, AutoTokenizer

app = Flask(__name__)

# تحميل النموذج والـ Tokenizer محلياً
MODEL_NAME = "Qwen/Qwen2.5-1.5B-Instruct"
print("⏳ جاري تحميل النموذج...")

tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForCausalLM.from_pretrained(
    MODEL_NAME, torch_dtype=torch.float16, device_map="auto"
)

print("✅ النموذج جاهز للعمل!")


@app.route("/")
def home():
  return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
  data = request.json
  user_message = data.get("message", "")
  history = data.get("history", [])

  if not user_message.strip():
    return jsonify({"response": "الرجاء إدخال رسالة صحيحة."})

  # تجهيز المحادثة بالقالب المناسب
  chat_history = [{"role": "system", "content": "أنت مساعد ذكي ومفيد."}]
  for h in history:
    chat_history.append({"role": h["role"], "content": h["content"]})

  chat_history.append({"role": "user", "content": user_message})

  text = tokenizer.apply_chat_template(
      chat_history, tokenize=False, add_generation_prompt=True
  )

  model_inputs = tokenizer([text], return_tensors="pt").to(model.device)

  generated_ids = model.generate(
      **model_inputs, max_new_tokens=512, temperature=0.7, top_p=0.9
  )

  generated_ids = [
      output_ids[len(input_ids) :]
      for input_ids, output_ids in zip(
          model_inputs.input_ids, generated_ids
      )
  ]
  response = tokenizer.batch_decode(
      generated_ids, skip_special_tokens=True
  )[0]

  return jsonify({"response": response})


if __name__ == "__main__":
  app.run(host="0.0.0.0", port=5000, debug=False)
