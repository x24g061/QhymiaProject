document.addEventListener("DOMContentLoaded", function () {

    const chatMessages = document.getElementById("chat-messages");
    const chatInput = document.getElementById("chat-input");
    const chatSendButton = document.getElementById("chat-send-button");
    const chatError = document.getElementById("chat-error");

    if (!chatMessages || !chatInput || !chatSendButton) {
        return;
    }


    // ========================================
    // CSRFトークン取得
    // ========================================

    function getCookie(name) {
        let cookieValue = null;

        if (document.cookie && document.cookie !== "") {

            const cookies = document.cookie.split(";");

            for (let i = 0; i < cookies.length; i++) {

                const cookie = cookies[i].trim();

                if (cookie.startsWith(name + "=")) {
                    cookieValue = decodeURIComponent(
                        cookie.substring(name.length + 1)
                    );

                    break;
                }
            }
        }

        return cookieValue;
    }


    // ========================================
    // メッセージ表示
    // ========================================

    function renderMessages(messages) {

        chatMessages.innerHTML = "";

        if (messages.length === 0) {

            chatMessages.innerHTML = `
                <p class="chat-empty">
                    まだメッセージはありません。
                </p>
            `;

            return;
        }

        messages.forEach(function (chat) {

            const item = document.createElement("div");
            item.classList.add("chat-message");

            const header = document.createElement("div");
            header.classList.add("chat-message-header");

            const name = document.createElement("strong");
            name.textContent = chat.character_name;

            const time = document.createElement("span");
            time.textContent = chat.created_at;

            const text = document.createElement("p");
            text.textContent = chat.message;

            header.appendChild(name);
            header.appendChild(time);

            item.appendChild(header);
            item.appendChild(text);

            chatMessages.appendChild(item);
        });

        // 一番下までスクロール
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }


    // ========================================
    // メッセージ取得
    // ========================================

    async function loadMessages() {

        try {

            const response = await fetch("/chat/messages/");

            if (!response.ok) {
                throw new Error("メッセージ取得に失敗しました");
            }

            const data = await response.json();

            renderMessages(data.messages);

        } catch (error) {

            console.error(error);

        }
    }


    // ========================================
    // メッセージ送信
    // ========================================

    async function sendMessage() {

        const message = chatInput.value.trim();

        if (!message) {
            chatError.textContent = "メッセージを入力してください。";
            return;
        }

        chatError.textContent = "";
        chatSendButton.disabled = true;

        try {

            const response = await fetch("/chat/send/", {

                method: "POST",

                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCookie("csrftoken")
                },

                body: JSON.stringify({
                    message: message
                })

            });

            const data = await response.json();

            if (!response.ok) {

                chatError.textContent =
                    data.error || "送信に失敗しました。";

                return;
            }

            chatInput.value = "";

            await loadMessages();

        } catch (error) {

            console.error(error);

            chatError.textContent =
                "通信エラーが発生しました。";

        } finally {

            chatSendButton.disabled = false;

        }
    }


    // ========================================
    // 送信ボタン
    // ========================================

    chatSendButton.addEventListener("click", function () {
        sendMessage();
    });


    // Enterキーでも送信
    chatInput.addEventListener("keydown", function (event) {

        if (event.key === "Enter") {

            event.preventDefault();

            sendMessage();
        }
    });


    // ========================================
    // 初回読み込み
    // ========================================

    loadMessages();


    // ========================================
    // 5秒ごとに自動更新
    // ========================================

    setInterval(function () {
        loadMessages();
    }, 5000);

});