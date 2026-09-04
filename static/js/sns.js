document.addEventListener("DOMContentLoaded", function () {

    const miniSns = document.getElementById("mini-sns");
    const minimizeButton = document.getElementById("sns-minimize");
    const closeButton = document.getElementById("sns-close");
    const openHomeButton = document.getElementById("sns-open-home");

    if (!miniSns) {
        return;
    }


    // =====================
    // 保存状態を読み込む
    // =====================

    const savedState = localStorage.getItem("qhymiaMiniSnsState");

    if (!savedState) {
        miniSns.classList.add("hidden");
    }

    if (savedState === "minimized") {
        miniSns.classList.add("minimized");
        minimizeButton.textContent = "□";
    }

    if (savedState === "closed") {
        miniSns.classList.add("hidden");
    }


    // =====================
    // 保存していた位置を復元
    // =====================

    const savedLeft = localStorage.getItem("qhymiaMiniSnsLeft");
    const savedTop = localStorage.getItem("qhymiaMiniSnsTop");

    if (savedLeft && savedTop) {
        miniSns.style.left = savedLeft + "px";
        miniSns.style.top = savedTop + "px";
        miniSns.style.right = "auto";
        miniSns.style.bottom = "auto";
    }


    // =====================
    // ホームからSNSを開く
    // =====================

    if (openHomeButton) {
        openHomeButton.addEventListener("click", function () {

            miniSns.classList.remove("hidden");
            miniSns.classList.remove("minimized");

            minimizeButton.textContent = "−";

            localStorage.setItem(
                "qhymiaMiniSnsState",
                "open"
            );
        });
    }


    // =====================
    // 最小化
    // =====================

    minimizeButton.addEventListener("click", function () {

        const isMinimized =
            miniSns.classList.toggle("minimized");

        if (isMinimized) {

            minimizeButton.textContent = "□";

            localStorage.setItem(
                "qhymiaMiniSnsState",
                "minimized"
            );

        } else {

            minimizeButton.textContent = "−";

            localStorage.setItem(
                "qhymiaMiniSnsState",
                "open"
            );
        }
    });


    // =====================
    // 閉じる
    // =====================

    closeButton.addEventListener("click", function () {

        miniSns.classList.add("hidden");
        miniSns.classList.remove("minimized");

        minimizeButton.textContent = "−";

        localStorage.setItem(
            "qhymiaMiniSnsState",
            "closed"
        );
    });


    // =====================
    // SNSをドラッグ移動
    // =====================

    const snsHeader = miniSns.querySelector(".mini-sns-header");

    let isDragging = false;
    let offsetX = 0;
    let offsetY = 0;


    snsHeader.addEventListener("mousedown", function (event) {

        // ボタンを押した時はドラッグしない
        if (event.target.closest("button")) {
            return;
        }

        isDragging = true;

        const rect = miniSns.getBoundingClientRect();

        offsetX = event.clientX - rect.left;
        offsetY = event.clientY - rect.top;

        miniSns.style.right = "auto";
        miniSns.style.bottom = "auto";

        document.body.style.userSelect = "none";
    });


    document.addEventListener("mousemove", function (event) {

        if (!isDragging) {
            return;
        }

        let newLeft = event.clientX - offsetX;
        let newTop = event.clientY - offsetY;

        const maxLeft =
            window.innerWidth - miniSns.offsetWidth;

        const maxTop =
            window.innerHeight - miniSns.offsetHeight;

        newLeft = Math.max(
            0,
            Math.min(newLeft, maxLeft)
        );

        newTop = Math.max(
            0,
            Math.min(newTop, maxTop)
        );

        miniSns.style.left = newLeft + "px";
        miniSns.style.top = newTop + "px";
    });


    document.addEventListener("mouseup", function () {

        if (!isDragging) {
            return;
        }

        isDragging = false;

        document.body.style.userSelect = "";

        const rect = miniSns.getBoundingClientRect();

        localStorage.setItem(
            "qhymiaMiniSnsLeft",
            rect.left
        );

        localStorage.setItem(
            "qhymiaMiniSnsTop",
            rect.top
        );
    });

});