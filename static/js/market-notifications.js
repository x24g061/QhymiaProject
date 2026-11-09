
/* ========================================
   Qhymia フリーマーケット
   リアルタイム売却通知
======================================== */

document.addEventListener("DOMContentLoaded", () => {

    const protocol =
        location.protocol === "https:" ? "wss:" : "ws:";

    const websocketUrl =
        `${protocol}//${location.host}/ws/market-notifications/`;

    // 通知表示エリアを作成
    const notificationArea = document.createElement("div");
    notificationArea.id = "market-notification-area";
    notificationArea.setAttribute("aria-live", "polite");

    document.body.appendChild(notificationArea);

    let socket = null;
    let reconnectTimer = null;
    let reconnectAttempts = 0;
    let stopped = false;

    // ========================================
    // 通知ポップアップ表示
    // ========================================

    function showNotification(message) {

        const notification = document.createElement("div");
        notification.className = "market-realtime-toast";

        const heading = document.createElement("div");
        heading.className = "market-toast-heading";

        const icon = document.createElement("span");
        icon.textContent = "🔔";

        const title = document.createElement("strong");
        title.textContent = "商品が売れました！";

        heading.appendChild(icon);
        heading.appendChild(title);

        const content = document.createElement("p");
        content.textContent = message;

        const closeButton = document.createElement("button");
        closeButton.type = "button";
        closeButton.className = "market-toast-close";
        closeButton.textContent = "×";
        closeButton.setAttribute("aria-label", "通知を閉じる");

        const removeNotification = () => {
            notification.remove();
        };

        closeButton.addEventListener(
            "click",
            removeNotification
        );

        notification.appendChild(closeButton);
        notification.appendChild(heading);
        notification.appendChild(content);

        notificationArea.prepend(notification);

        // 8秒後に自動で閉じる
        setTimeout(removeNotification, 8000);
    }

    // ========================================
    // WebSocket接続
    // ========================================

    function connect() {

        if (stopped) {
            return;
        }

        socket = new WebSocket(websocketUrl);

        socket.onopen = () => {
            reconnectAttempts = 0;
            console.log("売却通知WebSocket接続成功");
        };

        socket.onmessage = (event) => {

            let data;

            try {
                data = JSON.parse(event.data);
            } catch (error) {
                console.error("通知データの解析に失敗", error);
                return;
            }

            if (
                data.type === "sale_notification" &&
                typeof data.message === "string"
            ) {
                showNotification(data.message);
            }
        };

        socket.onerror = () => {
            console.warn("売却通知WebSocketでエラー発生");
        };

        socket.onclose = (event) => {

            if (stopped || event.code === 4401) {
                return;
            }

            // 接続が切れた場合、一定時間後に再接続
            reconnectAttempts += 1;

            const delay = Math.min(
                1000 * (2 ** Math.min(reconnectAttempts, 5)),
                30000
            );

            reconnectTimer = setTimeout(connect, delay);
        };
    }

    // ページ離脱時は再接続しない
    window.addEventListener("pagehide", () => {
        stopped = true;
        clearTimeout(reconnectTimer);

        if (socket) {
            socket.close();
        }
    });

    connect();
});
