import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

# اختيار نموذج مفتوح المصدر خفيف وقوي (يدعم العربية والإنجليزية بامتياز)
MODEL_NAME = "Qwen/Qwen2.5-1.5B-Instruct"

print("⏳ جاري تحميل النموذج والذكاء الاصطناعي محلياً، يرجى الانتظار...")

# تحميل الـ Tokenizer والنموذج
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForCausalLM.from_pretrained(
    MODEL_NAME,
    torch_dtype=torch.float16,
    device_map="auto"
)

print("\n🤖 الذكاء الاصطناعي المحلي جاهز! اكتب سؤالك (أو اكتب 'خروج' للإنهاء).\n" + "-"*50)

# حافظة لتاريخ المحادثة (سياق الشات)
chat_history = [
    {"role": "system", "content": "أنت مساعد ذكي ومفيد تتحدث باللغة العربية."}
]

while True:
    user_input = input("أنت: ")
    if user_input.strip().lower() in ['خروج', 'exit', 'quit']:
        print("مع السلامة!")
        break
    
    if not user_input.strip():
        continue

    # إضافة رسالة المستخدم للسياق
    chat_history.append({"role": "user", "content": user_input})

    # تجهيز المدخلات باستخدام قوالب النموذج الرسمية
    text = tokenizer.apply_chat_template(
        chat_history,
        tokenize=False,
        add_generation_prompt=True
    )
    
    model_inputs = tokenizer([text], return_tensors="pt").to(model.device)

    # توليد الرد
    generated_ids = model.generate(
        **model_inputs,
        max_new_tokens=512,
        temperature=0.7,
        top_p=0.9
    )
    
    # استخراج الرد الجديد فقط بدون مدخلات المستخدم
    generated_ids = [
        output_ids[len(input_ids):] for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)
    ]
    
    response = tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]
    
    print(f"المساعد: {response}\n" + "-"*50)
    
    # إضافة رد المساعد لتاريخ المحادثة ليفهم السياق في المرات القادمة
    chat_history.append({"role": "assistant", "content": response})
