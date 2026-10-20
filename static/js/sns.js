document.addEventListener("DOMContentLoaded", function () {

    const miniSns =
        document.getElementById("mini-sns");

    const minimizeButton =
        document.getElementById("sns-minimize");

    const closeButton =
        document.getElementById("sns-close");

    const openHomeButton =
        document.getElementById("sns-open-home");

    const refreshButton =
        document.getElementById(
            "mini-sns-refresh"
        );

    const refreshLogoButton =
        document.getElementById(
            "mini-sns-refresh-logo"
        );

    const postList =
        document.getElementById(
            "mini-sns-post-list"
        );


    if (!miniSns) {
        return;
    }


    // =====================
    // CSRF
    // =====================

    function getCookie(name) {

        const cookies =
            document.cookie.split(";");

        for (let cookie of cookies) {

            cookie = cookie.trim();

            if (
                cookie.startsWith(
                    name + "="
                )
            ) {

                return decodeURIComponent(
                    cookie.substring(
                        name.length + 1
                    )
                );

            }

        }

        return null;
    }

    // =====================
    // ミニSNSだけ更新
    // =====================

    async function refreshMiniSns() {

        if (
            !postList ||
            !miniSns.dataset.refreshUrl
        ) {
            return;
        }

        if (refreshButton) {

            refreshButton.disabled =
                true;

            refreshButton.classList.add(
                "is-refreshing"
            );
        }

        try {

            const response =
                await fetch(
                    miniSns.dataset.refreshUrl,
                    {
                        method: "GET",

                        headers: {
                            "X-Requested-With":
                                "XMLHttpRequest",
                        },

                        cache: "no-store",
                    }
                );

            if (!response.ok) {

                throw new Error(
                    "ミニSNSの更新に失敗しました。"
                );
            }

            const html =
                await response.text();

            postList.innerHTML =
                html;

        } catch (error) {

            console.error(
                error
            );

        } finally {

            if (refreshButton) {

                refreshButton.disabled =
                    false;

                refreshButton.classList.remove(
                    "is-refreshing"
                );
            }
        }
    }


    // =====================
    // 更新ボタン
    // =====================

    if (refreshButton) {

        refreshButton.addEventListener(
            "click",
            refreshMiniSns
        );
    }


    // =====================
    // Qhymia SNSロゴ
    // =====================

    if (refreshLogoButton) {

        refreshLogoButton.addEventListener(
            "click",
            refreshMiniSns
        );
    }


    // =====================
    // 保存状態
    // =====================

    const savedState =
        localStorage.getItem(
            "qhymiaMiniSnsState"
        );


    if (!savedState) {
        miniSns.classList.add(
            "hidden"
        );
    }


    if (
        savedState ===
        "minimized"
    ) {

        miniSns.classList.add(
            "minimized"
        );

        minimizeButton.textContent =
            "□";
    }


    if (
        savedState ===
        "closed"
    ) {

        miniSns.classList.add(
            "hidden"
        );
    }


    // =====================
    // 保存位置
    // =====================

    const savedLeft =
        localStorage.getItem(
            "qhymiaMiniSnsLeft"
        );

    const savedTop =
        localStorage.getItem(
            "qhymiaMiniSnsTop"
        );


    if (
        savedLeft &&
        savedTop
    ) {

        miniSns.style.left =
            savedLeft + "px";

        miniSns.style.top =
            savedTop + "px";

        miniSns.style.right =
            "auto";

        miniSns.style.bottom =
            "auto";
    }


    // =====================
    // ホームから開く
    // =====================

    if (openHomeButton) {

        openHomeButton.addEventListener(
            "click",
            function () {

                miniSns.classList.remove(
                    "hidden"
                );

                miniSns.classList.remove(
                    "minimized"
                );

                minimizeButton.textContent =
                    "−";

                localStorage.setItem(
                    "qhymiaMiniSnsState",
                    "open"
                );

            }
        );
    }


    // =====================
    // 最小化
    // =====================

    minimizeButton.addEventListener(
        "click",
        function () {

            const isMinimized =
                miniSns.classList.toggle(
                    "minimized"
                );


            if (isMinimized) {

                minimizeButton.textContent =
                    "□";

                localStorage.setItem(
                    "qhymiaMiniSnsState",
                    "minimized"
                );

            } else {

                minimizeButton.textContent =
                    "−";

                localStorage.setItem(
                    "qhymiaMiniSnsState",
                    "open"
                );

            }

        }
    );


    // =====================
    // 閉じる
    // =====================

    closeButton.addEventListener(
        "click",
        function () {

            miniSns.classList.add(
                "hidden"
            );

            miniSns.classList.remove(
                "minimized"
            );

            minimizeButton.textContent =
                "−";

            localStorage.setItem(
                "qhymiaMiniSnsState",
                "closed"
            );

        }
    );


    // =====================
    // ミニSNSから投稿
    // =====================

    const postForm =
        document.getElementById(
            "mini-sns-post-form"
        );

    const postError =
        document.getElementById(
            "mini-sns-post-error"
        );


    if (postForm) {

        postForm.addEventListener(
            "submit",
            async function (event) {

                event.preventDefault();


                const submitButton =
                    postForm.querySelector(
                        ".mini-sns-submit-button"
                    );


                submitButton.disabled =
                    true;

                postError.textContent =
                    "";


                try {

                    const formData =
                        new FormData(
                            postForm
                        );


                    const response =
                        await fetch(
                            postForm.action,
                            {
                                method:
                                    "POST",

                                headers: {
                                    "X-CSRFToken":
                                        getCookie(
                                            "csrftoken"
                                        ),

                                    "X-Requested-With":
                                        "XMLHttpRequest",
                                },

                                body:
                                    formData,
                            }
                        );


                    const data =
                        await response.json();


                    if (
                        !response.ok ||
                        !data.success
                    ) {

                        throw new Error(
                            data.error ||
                            "投稿に失敗しました。"
                        );

                    }


                    postForm.reset();

                    localStorage.setItem(
                        "qhymiaMiniSnsState",
                        "open"
                    );

                    await refreshMiniSns();


                } catch (error) {

                    postError.textContent =
                        error.message;

                } finally {

                    submitButton.disabled =
                        false;

                }

            }
        );

    }


// =====================
// 投稿操作
// 更新後の投稿にも対応
// =====================

miniSns.addEventListener(
    "click",
    async function (event) {


        // =====================
        // いいね
        // =====================

        const likeButton =
            event.target.closest(
                ".mini-like-button"
            );

        if (likeButton) {

            const response =
                await fetch(
                    likeButton.dataset.url,
                    {
                        method: "POST",

                        headers: {
                            "X-CSRFToken":
                                getCookie(
                                    "csrftoken"
                                ),

                            "X-Requested-With":
                                "XMLHttpRequest",
                        },
                    }
                );

            if (!response.ok) {
                return;
            }

            const data =
                await response.json();

            const icon =
                likeButton.querySelector(
                    ".mini-like-icon"
                );

            const count =
                likeButton.querySelector(
                    ".mini-like-count"
                );

            icon.textContent =
                data.liked
                    ? "♥"
                    : "♡";

            count.textContent =
                data.like_count;

            return;
        }


        // =====================
        // お気に入り
        // =====================

        const favoriteButton =
            event.target.closest(
                ".mini-favorite-button"
            );

        if (favoriteButton) {

            const response =
                await fetch(
                    favoriteButton.dataset.url,
                    {
                        method: "POST",

                        headers: {
                            "X-CSRFToken":
                                getCookie(
                                    "csrftoken"
                                ),

                            "X-Requested-With":
                                "XMLHttpRequest",
                        },
                    }
                );

            if (!response.ok) {
                return;
            }

            const data =
                await response.json();

            const icon =
                favoriteButton.querySelector(
                    ".mini-favorite-icon"
                );

            icon.textContent =
                data.favorited
                    ? "★"
                    : "☆";

            return;
        }


        // =====================
        // 削除
        // =====================

        const deleteButton =
            event.target.closest(
                ".mini-delete-button"
            );

        if (deleteButton) {

            const confirmed =
                window.confirm(
                    "この投稿を削除しますか？"
                );

            if (!confirmed) {
                return;
            }

            const response =
                await fetch(
                    deleteButton.dataset.url,
                    {
                        method: "POST",

                        headers: {
                            "X-CSRFToken":
                                getCookie(
                                    "csrftoken"
                                ),

                            "X-Requested-With":
                                "XMLHttpRequest",
                        },
                    }
                );

            if (!response.ok) {
                return;
            }

            const data =
                await response.json();

            if (data.success) {

                await refreshMiniSns();
            }

            return;
        }
    }
);
    // =====================
    // ドラッグ
    // =====================

    const snsHeader =
        miniSns.querySelector(
            ".mini-sns-header"
        );


    let isDragging =
        false;

    let offsetX =
        0;

    let offsetY =
        0;


    snsHeader.addEventListener(
        "mousedown",
        function (event) {

            if (
                event.target.closest(
                    "button"
                )
            ) {
                return;
            }


            isDragging =
                true;


            const rect =
                miniSns
                    .getBoundingClientRect();


            offsetX =
                event.clientX -
                rect.left;

            offsetY =
                event.clientY -
                rect.top;


            miniSns.style.right =
                "auto";

            miniSns.style.bottom =
                "auto";


            document.body.style.userSelect =
                "none";

        }
    );


    document.addEventListener(
        "mousemove",
        function (event) {

            if (!isDragging) {
                return;
            }


            let newLeft =
                event.clientX -
                offsetX;

            let newTop =
                event.clientY -
                offsetY;


            const maxLeft =
                window.innerWidth -
                miniSns.offsetWidth;

            const maxTop =
                window.innerHeight -
                miniSns.offsetHeight;


            newLeft =
                Math.max(
                    0,
                    Math.min(
                        newLeft,
                        maxLeft
                    )
                );


            newTop =
                Math.max(
                    0,
                    Math.min(
                        newTop,
                        maxTop
                    )
                );


            miniSns.style.left =
                newLeft + "px";

            miniSns.style.top =
                newTop + "px";

        }
    );


    document.addEventListener(
        "mouseup",
        function () {

            if (!isDragging) {
                return;
            }


            isDragging =
                false;


            document.body.style.userSelect =
                "";


            const rect =
                miniSns
                    .getBoundingClientRect();


            localStorage.setItem(
                "qhymiaMiniSnsLeft",
                rect.left
            );


            localStorage.setItem(
                "qhymiaMiniSnsTop",
                rect.top
            );

        }
    );

});