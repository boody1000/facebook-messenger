const axios = require('axios');

const VERIFY_TOKEN = "test1234";
const PAGE_ACCESS_TOKEN = "EAAYp9WGUwpMBSXQjb0zbdzZAWqcALJI5LkAIvn7PFBQA96k63XuBCSWMVgPEXWyj8lZAbebZCHC6HhTUukL2PdTXQo6o9N9KVIKZCBTom36lXZCffI8GzyoZBYubunZCXynhiZCSmxgx6aZB5fJrMn3oWPDUoUwhdJCiWK2IVvxHgsGUkZABuK0wn8h3ptriKtVpASdWZCF1TBGq1cgfJkfy4wa3yI8wlaiqNsNxEPeUiylGv821nAcC54D5AZDZD";
const FIREBASE_URL = "https://messeng-54eba-default-rtdb.firebaseio.com";

module.exports = async (req, res) => {
    // 1. مرحلة التحقق (GET Request من فيسبوك)
    if (req.method === 'GET') {
        const mode = req.query['hub_mode'] || req.query['hub.mode'];
        const token = req.query['hub_verify_token'] || req.query['hub.verify_token'];
        const challenge = req.query['hub_challenge'] || req.query['hub.challenge'];

        if (mode && token) {
            if (mode === 'subscribe' && token === VERIFY_TOKEN) {
                return res.status(200).send(challenge);
            } else {
                return res.status(403).send('Forbidden');
            }
        }
        return res.status(400).send('Bad Request');
    }

    // 2. استقبال الرسائل (POST Request من فيسبوك)
    if (req.method === 'POST') {
        const body = req.body;

        if (body.object === 'page') {
            for (const entry of body.entry) {
                if (entry.messaging) {
                    for (const webhookEvent of entry.messaging) {
                        if (webhookEvent.message && !webhookEvent.message.is_echo) {
                            const senderId = webhookEvent.sender.id;
                            const messageText = webhookEvent.message.text || '[مرفق/صورة]';

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
            return res.status(200).send('EVENT_RECEIVED');
        } else {
            return res.sendStatus(404);
        }
    }

    res.setHeader('Allow', ['GET', 'POST']);
    res.status(405).end(`Method ${req.method} Not Allowed`);
};
