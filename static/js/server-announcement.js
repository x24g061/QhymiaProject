document.addEventListener("DOMContentLoaded", function () {
    const bar = document.getElementById("server-announcement");
    const text = document.getElementById("server-announcement-text");

    if (!bar || !text) {
        return;
    }

    const apiUrl = bar.dataset.url;
    let currentMessage = "";

    async function updateAnnouncement() {
        try {
            const response = await fetch(apiUrl, {
                method: "GET",
                cache: "no-store",
                credentials: "same-origin"
            });

            if (!response.ok) {
                throw new Error("告知取得失敗");
            }

            const data = await response.json();

            if (!data.is_active || !data.message) {
                bar.hidden = true;
                currentMessage = "";
                text.textContent = "";
                return;
            }

            if (currentMessage !== data.message) {
                currentMessage = data.message;
                text.textContent = currentMessage;

                // 告知変更時にアニメーションを最初から再生
                text.style.animation = "none";
                void text.offsetWidth;
                text.style.animation = "";
            }

            bar.hidden = false;

        } catch (error) {
            console.warn("サーバー告知の取得に失敗しました:", error);
        } finally {
            setTimeout(updateAnnouncement, 5000);
        }
    }

    updateAnnouncement();
});
