import streamlit as st
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

# إعداد الصفحة
st.set_page_config(page_title="مساعدك الذكي المحلي", page_icon="🤖", layout="centered")

st.title("🤖 شات بوت ذكي محلي (Hugging Face)")
st.write("هذا التطبيق يعمل محلياً بالكامل باستخدام نماذج Hugging Face دون أي اعتماد على APIs خارجية.")

# اختيار النموذج وتحميله مرة واحدة وتخزينه مؤقتاً في الذاكرة لتسريع الأداء
@st.cache_resource
def load_model():
    model_name = "Qwen/Qwen2.5-1.5B-Instruct"
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(
        model_name, 
        torch_dtype=torch.float16, 
        device_map="auto"
    )
    return tokenizer, model

with st.spinner("⏳ جاري تحميل النموذج والذكاء الاصطناعي محلياً، يرجى الانتظار..."):
    tokenizer, model = load_model()

st.success("✅ النموذج جاهز للعمل!")

# تهيئة الذاكرة لحفظ رسائل الشات
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "system", "content": "أنت مساعد ذكي ومفيد."}
    ]

# عرض رسائل الشات السابقة (باستثناء رسالة الـ system)
for message in st.session_state.messages:
    if message["role"] != "system":
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

# استقبال رسالة المستخدم الجديدة
if user_input := st.chat_input("اكتب رسالتك هنا..."):
    # عرض رسالة المستخدم في الواجهة
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # توليد الرد من النموذج المحلي
    with st.chat_message("assistant"):
        with st.spinner("جاري التفكير والتوليد..."):
            try:
                # تطبيق قالب المحادثة الخاص بالنموذج
                text = tokenizer.apply_chat_template(
                    st.session_state.messages,
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
                
                generated_ids = [
                    output_ids[len(input_ids):] for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)
                ]
                
                response = tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]
                
                st.markdown(response)
                
                # حفظ رد المساعد في الذاكرة
                st.session_state.messages.append({"role": "assistant", "content": response})
                
            except Exception as e:
                st.error(f"حدث خطأ أثناء توليد الرد: {e}")
