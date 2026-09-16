// الانتظار حتى تحميل الصفحة الـ iframe والـ DOM
window.addEventListener('DOMContentLoaded', () => {
    const fbIframe = document.getElementById('fb-iframe');

    // ملاحظة أمنية: الـ iframe يعمل بشكل كامل إذا كان ضمن نفس النطاق أو مسموح بالـ CORS، 
    // وفي البيئة المحلية أو لوحة التحكم الخاصة بك يمكنك تفعيل السكربت بمنتهى السهولة.
    
    fbIframe.addEventListener('load', () => {
        try {
            const fbDoc = fbIframe.contentDocument || fbIframe.contentWindow.document;
            
            // مراقبة الرسائل الواردة باستخدام MutationObserver
            const chatListArea = fbDoc.body; // يتم تحديد الـ Container الدقيق لصندوق الدردشة حسب كود فيسبوك
            
            const observer = new MutationObserver((mutations) => {
                mutations.forEach((mutation) => {
                    if (mutation.addedNodes.length > 0) {
                        // تتبع العناصر الجديدة المضافة (الرسائل)
                        mutation.addedNodes.forEach(node => {
                            if (node.nodeType === 1 && node.innerText) {
                                // فلترة واكتشاف الرسائل الواردة وعرضها في واجهتك
                                displayLiveMessage(node.innerText);
                            }
                        });
                    }
                });
            });

            // مراقبة التغيرات في صندوق الدردشة بفيسبوك
            observer.observe(chatListArea, { childList: true, subtree: true });

        } catch (e) {
            console.log("سياسات الأمان المتصفح تتطلب تشغيل السكربت كـ Extension أو ضمن نفس النطاق المباشر:", e);
        }
    });
});

// عرض الرسالة في واجهة موقعك الحية بدون تخزين
function displayLiveMessage(text) {
    const box = document.getElementById('live-messages-box');
    const msgDiv = document.createElement('div0');
    
    // تنظيف المكان المخصص لو في رسالة "في انتظار..."
    if(box.querySelector('.text-gray-400')) {
        box.innerHTML = '';
    }

    const bubble = document.createElement('div');
    bubble.className = "bg-white p-3 rounded-lg shadow-sm border border-gray-200 text-sm text-gray-800 max-w-[80%] inline-block";
    bubble.innerText = text;
    
    box.appendChild(bubble);
    box.scrollTop = box.scrollHeight; // النزول لأسفل القائمة تلقائياً
}

// دالة إرسال الرد المباشر لفيسبوك
function sendReply() {
    const input = document.getElementById('reply-input');
    const text = input.value.trim();
    if (!text) return;

    try {
        const fbIframe = document.getElementById('fb-iframe');
        const fbDoc = fbIframe.contentDocument || fbIframe.contentWindow.document;
        
        // الوصول إلى حقل كتابة الرسائل في واجهة فيسبوك (يتم مطابقة الـ Selector الخاص بـ Meta Business Suite)
        const fbInputBox = fbDoc.querySelector('div[contenteditable="true"]');
        
        if (fbInputBox) {
            fbInputBox.focus();
            fbInputBox.innerHTML = text;
            
            // محاكاة حدث الكتابة والضغط على زر الإرسال أو زر Enter
            fbInputBox.dispatchEvent(new Event('input', { bubbles: true }));
            
            setTimeout(() => {
                const enterEvent = new KeyboardEvent('keydown', {
                    bubbles: true, cancelable: true, keyCode: 13, key: 'Enter'
                });
                fbInputBox.dispatchEvent(enterEvent);
                
                // تفريغ خانة الكتابة في موقعك
                input.value = '';
            }, 200);
        } else {
            alert('يرجى تحديد المحادثة النشطة داخل نافذة فيسبوك أولاً.');
        }
    } catch (e) {
        alert('خطأ في الاتصال بإطار فيسبوك الداخلي بسبب قيود المتصفح.');
    }
}
