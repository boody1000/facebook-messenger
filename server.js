const express = require('express');
const bodyParser = require('body-parser');
const axios = require('axios');

const app = express();
app.use(bodyParser.json());

const VERIFY_TOKEN = "test1234";
const PAGE_ACCESS_TOKEN = "EAAYp9WGUwpMBSXQjb0zbdzZAWqcALJI5LkAIvn7PFBQA96k63XuBCSWMVgPEXWyj8lZAbebZCHC6HhTUukL2PdTXQo6o9N9KVIKZCBTom36lXZCffI8GzyoZBYubunZCXynhiZCSmxgx6aZB5fJrMn3oWPDUoUwhdJCiWK2IVvxHgsGUkZABuK0wn8h3ptriKtVpASdWZCF1TBGq1cgfJkfy4wa3yI8wlaiqNsNxEPeUiylGv821nAcC54D5AZDZD";
const FIREBASE_URL = "https://messeng-54eba-default-rtdb.firebaseio.com";

// 1. نقطة التحقق (Webhook Verification) من فيسبوك
app.get('/webhook', (req, res) => {
    const mode = req.query['hub.mode'];
    const token = req.query['hub.verify_token'];
    const challenge = req.query['hub.challenge'];

    if (mode && token) {
        if (mode === 'subscribe' && token === VERIFY_TOKEN) {
            console.log('WEBHOOK_VERIFIED');
            res.status(200).send(challenge);
        } else {
            res.sendStatus(403);
        }
    } else {
        res.sendStatus(400);
    }
});

// 2. استقبال الرسائل القادمة وتوجيهها لـ Firebase
app.post('/webhook', async (req, res) => {
    const body = req.body;

    if (body.object === 'page') {
        for (const entry of body.entry) {
            if (entry.messaging) {
                for (const webhookEvent of entry.messaging) {
                    if (webhookEvent.message && !webhookEvent.message.is_echo) {
                        const senderId = webhookEvent.sender.id;
                        const messageText = webhookEvent.message.text || '[مرفق/صورة]';

                        // جلب اسم العميل من فيسبوك
                        let senderName = "عميل مسنجر";
                        try {
                            const profileRes = await axios.get(`https://graph.facebook.com/v18.0/${senderId}?fields=first_name,last_name&access_token=${PAGE_ACCESS_TOKEN}`);
                            if (profileRes.data && profileRes.data.first_name) {
                                senderName = `${profileRes.data.first_name} ${profileRes.data.last_name || ''}`;
                            }
                        } catch (e) {
                            console.log("Error fetching profile", e.message);
                        }

                        const timeString = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

                        // إرسال البيانات لفايربيز
                        await axios.post(`${FIREBASE_URL}/messages/${senderId}.json`, {
                            message_text: messageText,
                            sender_type: "client",
                            sender_name: senderName.trim(),
                            created_time: timeString
                        });
                    }
                }
            }
        }
        res.status(200).send('EVENT_RECEIVED');
    } else {
        res.sendStatus(404);
    }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`Server is running on port ${PORT}`));
