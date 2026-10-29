document.addEventListener(
    "DOMContentLoaded",
    function () {

        const chatMessages =
            document.getElementById(
                "chat-messages"
            );

        const chatInput =
            document.getElementById(
                "chat-input"
            );

        const chatSendButton =
            document.getElementById(
                "chat-send-button"
            );

        const chatError =
            document.getElementById(
                "chat-error"
            );


        if (
            !chatMessages ||
            !chatInput ||
            !chatSendButton
        ) {
            return;
        }


        // ========================================
        // 表示済みメッセージID
        // ========================================

        const displayedMessageIds =
            new Set();


        // ========================================
        // WebSocket
        // ========================================

        let chatSocket = null;

        let reconnectTimer = null;


        // ========================================
        // メッセージ1件を画面へ追加
        // ========================================

        function appendMessage(chat) {

            // 同じメッセージを二重表示しない
            if (
                displayedMessageIds.has(
                    chat.id
                )
            ) {
                return;
            }

            displayedMessageIds.add(
                chat.id
            );


            const item =
                document.createElement(
                    "div"
                );

            item.classList.add(
                "chat-message"
            );


            // ========================================
            // アイコン + メッセージ本体
            // ========================================

            const body =
                document.createElement(
                    "div"
                );

            body.classList.add(
                "chat-message-body"
            );


            // キャラクターアイコン
            const avatar =
                document.createElement(
                    "div"
                );

            avatar.classList.add(
                "chat-message-avatar"
            );


            if (
                chat.character_image_url
            ) {

                const image =
                    document.createElement(
                        "img"
                    );

                image.src =
                    chat.character_image_url;

                image.alt =
                    chat.character_name;

                avatar.appendChild(
                    image
                );

            } else {

                const fallback =
                    document.createElement(
                        "span"
                    );

                fallback.textContent =
                    chat.character_name
                        ? chat.character_name.charAt(
                            0
                        )
                        : "?";

                avatar.appendChild(
                    fallback
                );
            }


            // ========================================
            // 右側本文
            // ========================================

            const content =
                document.createElement(
                    "div"
                );

            content.classList.add(
                "chat-message-content"
            );


            const header =
                document.createElement(
                    "div"
                );

            header.classList.add(
                "chat-message-header"
            );


            const name =
                document.createElement(
                    "strong"
                );

            name.textContent =
                chat.character_name;


            const time =
                document.createElement(
                    "span"
                );

            time.textContent =
                chat.created_at;


            const text =
                document.createElement(
                    "p"
                );

            text.textContent =
                chat.message;


            header.appendChild(
                name
            );

            header.appendChild(
                time
            );

            content.appendChild(
                header
            );

            content.appendChild(
                text
            );

            body.appendChild(
                avatar
            );

            body.appendChild(
                content
            );

            item.appendChild(
                body
            );

            chatMessages.appendChild(
                item
            );
        }


        // ========================================
        // 一番下までスクロール
        // ========================================

        function scrollToBottom() {

            chatMessages.scrollTop =
                chatMessages.scrollHeight;
        }


        // ========================================
        // 初回50件取得
        // Fetch API
        // ========================================

        async function loadInitialMessages() {

            try {

                const response =
                    await fetch(
                        "/chat/messages/",
                        {
                            cache: "no-store"
                        }
                    );


                if (!response.ok) {

                    throw new Error(
                        "メッセージ取得に失敗しました"
                    );
                }


                const data =
                    await response.json();


                chatMessages.innerHTML =
                    "";

                displayedMessageIds.clear();


                if (
                    data.messages.length === 0
                ) {

                    chatMessages.innerHTML =
                        `
                        <p class="chat-empty">
                            まだメッセージはありません。
                        </p>
                        `;

                    return;
                }


                data.messages.forEach(
                    function (chat) {

                        appendMessage(
                            chat
                        );

                    }
                );


                scrollToBottom();


            } catch (error) {

                console.error(
                    error
                );

                chatError.textContent =
                    "チャットの読み込みに失敗しました。";
            }
        }


        // ========================================
        // WebSocket接続
        // ========================================

        function connectWebSocket() {

            // http → ws
            // https → wss
            const protocol =
                window.location.protocol ===
                "https:"
                    ? "wss"
                    : "ws";


            const socketUrl =
                protocol
                + "://"
                + window.location.host
                + "/ws/chat/";


            chatSocket =
                new WebSocket(
                    socketUrl
                );


            // ========================================
            // 接続成功
            // ========================================

            chatSocket.addEventListener(
                "open",
                function () {

                    console.log(
                        "オープンチャット WebSocket接続成功"
                    );

                    chatError.textContent =
                        "";

                }
            );


            // ========================================
            // サーバーから受信
            // ========================================

            chatSocket.addEventListener(
                "message",
                function (event) {

                    const data =
                        JSON.parse(
                            event.data
                        );


                    // エラー
                    if (
                        data.type ===
                        "error"
                    ) {

                        chatError.textContent =
                            data.error;

                        return;
                    }


                    // 新着チャット
                    if (
                        data.type ===
                        "chat_message"
                    ) {

                        const emptyMessage =
                            chatMessages.querySelector(
                                ".chat-empty"
                            );


                        if (emptyMessage) {

                            emptyMessage.remove();

                        }


                        appendMessage(
                            data.message
                        );


                        scrollToBottom();

                    }

                }
            );


            // ========================================
            // WebSocket切断
            // ========================================

            chatSocket.addEventListener(
                "close",
                function () {

                    console.log(
                        "WebSocket切断"
                    );


                    chatError.textContent =
                        "チャットへ再接続しています...";


                    // 2秒後に再接続
                    clearTimeout(
                        reconnectTimer
                    );


                    reconnectTimer =
                        setTimeout(
                            function () {

                                connectWebSocket();

                            },
                            2000
                        );

                }
            );


            // ========================================
            // WebSocketエラー
            // ========================================

            chatSocket.addEventListener(
                "error",
                function (error) {

                    console.error(
                        "WebSocketエラー",
                        error
                    );

                }
            );
        }


        // ========================================
        // メッセージ送信
        // ========================================

        function sendMessage() {

            const message =
                chatInput.value.trim();


            if (!message) {

                chatError.textContent =
                    "メッセージを入力してください。";

                return;
            }


            // WebSocket未接続
            if (
                !chatSocket ||
                chatSocket.readyState !==
                    WebSocket.OPEN
            ) {

                chatError.textContent =
                    "チャットサーバーへ接続中です。";

                return;
            }


            chatError.textContent =
                "";


            // ========================================
            // WebSocketでサーバーへ送信
            // ========================================

            chatSocket.send(
                JSON.stringify(
                    {
                        message:
                            message
                    }
                )
            );


            chatInput.value =
                "";

        }


        // ========================================
        // 送信ボタン
        // ========================================

        chatSendButton.addEventListener(
            "click",
            function () {

                sendMessage();

            }
        );


        // ========================================
        // Enterキー送信
        // ========================================

        chatInput.addEventListener(
            "keydown",
            function (event) {

                if (
                    event.key ===
                    "Enter"
                ) {

                    event.preventDefault();

                    sendMessage();

                }

            }
        );


        // ========================================
        // 初回処理
        // ========================================

        async function initializeChat() {

            // 過去50件
            await loadInitialMessages();

            // 以降の新着はWebSocket
            connectWebSocket();

        }


        initializeChat();

    }
);