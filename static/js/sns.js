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

    const postList =
        document.getElementById(
            "mini-sns-post-list"
        );

    const composeToggle =
        document.getElementById(
            "mini-sns-compose-toggle"
        );

    const composePanel =
        document.getElementById(
            "mini-sns-compose-panel"
        );

    const imageModal =
        document.getElementById(
            "mini-sns-image-modal"
        );

    const imageModalImage =
        document.getElementById(
            "mini-sns-image-modal-image"
        );

    const imageModalClose =
        document.getElementById(
            "mini-sns-image-modal-close"
        );

    const imageModalPrev =
        document.getElementById(
            "mini-sns-image-modal-prev"
        );

    const imageModalNext =
        document.getElementById(
            "mini-sns-image-modal-next"
        );

    const imageModalCounter =
        document.getElementById(
            "mini-sns-image-modal-counter"
        );

    const imageModalCurrent =
        document.getElementById(
            "mini-sns-image-modal-current"
        );

    const imageModalTotal =
        document.getElementById(
            "mini-sns-image-modal-total"
        );


    let modalImages = [];

    let modalImageIndex = 0;


    if (!miniSns) {
        return;
    }

    // =====================
    // 現在表示中のSNSタブ
    // =====================

    let currentMiniSnsView =
        miniSns
            .querySelector(
                ".mini-sns-tab.active"
            )
            ?.dataset.view
        || "recommended";


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

    async function refreshMiniSns(
        view = currentMiniSnsView
    ) {

        if (
            !postList ||
            !miniSns.dataset.refreshUrl
        ) {
            return;
        }


        currentMiniSnsView =
            view;


        if (refreshButton) {

            refreshButton.disabled =
                true;

            refreshButton.classList.add(
                "is-refreshing"
            );
        }


        try {

            const url =
                new URL(
                    miniSns.dataset.refreshUrl,
                    window.location.origin
                );


            url.searchParams.set(
                "view",
                currentMiniSnsView
            );


            const response =
                await fetch(
                    url.toString(),
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


            // =====================
            // 選択中タブ更新
            // =====================

            miniSns
                .querySelectorAll(
                    ".mini-sns-tab"
                )
                .forEach(
                    function (tab) {

                        tab.classList.toggle(
                            "active",
                            tab.dataset.view ===
                            currentMiniSnsView
                        );

                    }
                );


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
            function () {

                refreshMiniSns(
                    currentMiniSnsView
                );

            }
        );
    }


    // =====================
    // おすすめ / 新着タブ
    // =====================

    miniSns
        .querySelectorAll(
            ".mini-sns-tab"
        )
        .forEach(
            function (tab) {

                tab.addEventListener(
                    "click",
                    function () {

                        const view =
                            tab.dataset.view;


                        refreshMiniSns(
                            view
                        );

                    }
                );

            }
        );

    // =====================
    // 投稿欄 開閉
    // =====================

    if (
        composeToggle &&
        composePanel
    ) {

        composeToggle.addEventListener(
            "click",
            function () {

                const isHidden =
                    composePanel.hidden;

                composePanel.hidden =
                    !isHidden;

                composeToggle.textContent =
                    isHidden
                        ? "▼"
                        : "▲";

                composeToggle.setAttribute(
                    "aria-expanded",
                    isHidden
                        ? "true"
                        : "false"
                );

            }
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

    const imageInput =
        document.getElementById(
            "mini-sns-image-input"
        );

    const imagePreview =
        document.getElementById(
            "mini-sns-image-preview"
        );

    const previewImage =
        document.getElementById(
            "mini-sns-preview-image"
        );

    const previewPrev =
        document.getElementById(
            "mini-sns-preview-prev"
        );

    const previewNext =
        document.getElementById(
            "mini-sns-preview-next"
        );

    const previewCurrent =
        document.getElementById(
            "mini-sns-preview-current"
        );

    const previewTotal =
        document.getElementById(
            "mini-sns-preview-total"
        );
    const previewRemove =
        document.getElementById(
            "mini-sns-preview-remove"
        );


    let selectedMiniSnsImages = [];

    let previewIndex = 0;

    const postError =
        document.getElementById(
            "mini-sns-post-error"
        );

    // =====================
    // 投稿画像プレビュー
    // =====================

    function updateMiniSnsPreview() {

        if (
            selectedMiniSnsImages.length === 0
        ) {

            imagePreview.hidden = true;

            return;
        }


        const file =
            selectedMiniSnsImages[
            previewIndex
            ];


        previewImage.src =
            URL.createObjectURL(
                file
            );


        imagePreview.hidden =
            false;


        previewCurrent.textContent =
            previewIndex + 1;

        previewTotal.textContent =
            selectedMiniSnsImages.length;


        previewPrev.hidden =
            previewIndex === 0;

        previewNext.hidden =
            previewIndex ===
            selectedMiniSnsImages.length - 1;
    }


    if (imageInput) {

        imageInput.addEventListener(
            "change",
            function () {

                const newImages =
                    Array.from(
                        imageInput.files
                    );


                newImages.forEach(
                    function (file) {

                        if (
                            selectedMiniSnsImages.length < 2
                        ) {

                            selectedMiniSnsImages.push(
                                file
                            );
                        }

                    }
                );


                previewIndex = 0;


                updateMiniSnsPreview();


                // 同じ画像をもう一度選べるようにする
                imageInput.value = "";

            }
        );
    }


    if (previewNext) {

        previewNext.addEventListener(
            "click",
            function () {

                if (
                    previewIndex <
                    selectedMiniSnsImages.length - 1
                ) {

                    previewIndex++;

                    updateMiniSnsPreview();
                }

            }
        );
    }


    if (previewPrev) {

        previewPrev.addEventListener(
            "click",
            function () {

                if (
                    previewIndex > 0
                ) {

                    previewIndex--;

                    updateMiniSnsPreview();
                }

            }
        );
    }

    // =====================
    // 添付画像を削除
    // =====================

    if (previewRemove) {

        previewRemove.addEventListener(
            "click",
            function () {

                if (
                    selectedMiniSnsImages.length === 0
                ) {
                    return;
                }


                selectedMiniSnsImages.splice(
                    previewIndex,
                    1
                );


                if (
                    previewIndex >=
                    selectedMiniSnsImages.length
                ) {

                    previewIndex =
                        Math.max(
                            0,
                            selectedMiniSnsImages.length - 1
                        );
                }


                if (
                    selectedMiniSnsImages.length === 0
                ) {

                    imagePreview.hidden = true;

                    previewImage.removeAttribute(
                        "src"
                    );

                    return;
                }


                updateMiniSnsPreview();

            }
        );
    }

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


                    formData.delete(
                        "image"
                    );

                    formData.delete(
                        "image2"
                    );


                    if (
                        selectedMiniSnsImages[0]
                    ) {

                        formData.append(
                            "image",
                            selectedMiniSnsImages[0]
                        );
                    }


                    if (
                        selectedMiniSnsImages[1]
                    ) {

                        formData.append(
                            "image2",
                            selectedMiniSnsImages[1]
                        );
                    }


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

                    selectedMiniSnsImages = [];

                    previewIndex = 0;

                    imagePreview.hidden = true;


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
// 全画面画像を更新
// =====================

function updateModalImage() {

    if (
        !imageModalImage ||
        modalImages.length === 0
    ) {
        return;
    }


    imageModalImage.src =
        modalImages[
            modalImageIndex
        ];


    // =====================
    // 左右ボタン
    // =====================

    if (imageModalPrev) {

        imageModalPrev.hidden =
            modalImages.length <= 1 ||
            modalImageIndex === 0;
    }


    if (imageModalNext) {

        imageModalNext.hidden =
            modalImages.length <= 1 ||
            modalImageIndex ===
                modalImages.length - 1;
    }


    // =====================
    // 枚数表示
    // =====================

    if (
        imageModalCounter &&
        imageModalCurrent &&
        imageModalTotal
    ) {

        imageModalCounter.hidden =
            modalImages.length <= 1;

        imageModalCurrent.textContent =
            modalImageIndex + 1;

        imageModalTotal.textContent =
            modalImages.length;
    }
}
    // =====================
    // 全画面画像を閉じる
    // =====================

    function closeMiniSnsImageModal() {

        if (
            !imageModal ||
            !imageModalImage
        ) {
            return;
        }


        imageModal.hidden =
            true;

        imageModalImage.removeAttribute(
            "src"
        );

        document.body.style.overflow =
            "";
    }


    if (imageModalClose) {

        imageModalClose.addEventListener(
            "click",
            closeMiniSnsImageModal
        );
    }

    // =====================
// 全画面画像 前へ
// =====================

if (imageModalPrev) {

    imageModalPrev.addEventListener(
        "click",
        function () {

            if (
                modalImageIndex > 0
            ) {

                modalImageIndex--;

                updateModalImage();
            }

        }
    );
}


// =====================
// 全画面画像 次へ
// =====================

if (imageModalNext) {

    imageModalNext.addEventListener(
        "click",
        function () {

            if (
                modalImageIndex <
                modalImages.length - 1
            ) {

                modalImageIndex++;

                updateModalImage();
            }

        }
    );
}
    // =====================
    // 背景クリックで閉じる
    // =====================

    if (imageModal) {

        imageModal.addEventListener(
            "click",
            function (event) {

                if (
                    event.target ===
                    imageModal
                ) {

                    closeMiniSnsImageModal();
                }

            }
        );
    }


    // =====================
    // Escキーで閉じる
    // =====================

    document.addEventListener(
        "keydown",
        function (event) {

            if (
                event.key === "Escape" &&
                imageModal &&
                !imageModal.hidden
            ) {

                closeMiniSnsImageModal();
            }

        }
    );
    // =====================
    // 投稿操作
    // 更新後の投稿にも対応
    // =====================

    miniSns.addEventListener(
        "click",
        async function (event) {

            // =====================
            // 投稿画像 全画面表示
            // =====================

            const clickedPostImage =
                event.target.closest(
                    ".mini-sns-post-image"
                );


            if (clickedPostImage) {

                if (
                    imageModal &&
                    imageModalImage
                ) {

                    const carousel =
                        clickedPostImage.closest(
                            ".mini-sns-carousel"
                        );


                    // =====================
                    // 2枚画像
                    // =====================

                    if (carousel) {

                        const slides =
                            Array.from(
                                carousel.querySelectorAll(
                                    ".mini-sns-slide"
                                )
                            );


                        modalImages =
                            slides.map(
                                function (slide) {

                                    return slide.src;

                                }
                            );


                        modalImageIndex =
                            slides.indexOf(
                                clickedPostImage
                            );


                        if (
                            modalImageIndex < 0
                        ) {

                            modalImageIndex = 0;
                        }


                        // =====================
                        // 1枚画像
                        // =====================

                    } else {

                        modalImages = [
                            clickedPostImage.src
                        ];

                        modalImageIndex = 0;
                    }


                    updateModalImage();


                    imageModal.hidden =
                        false;

                    document.body.style.overflow =
                        "hidden";
                }


                return;
            }
            // =====================
            // 投稿画像スライド
            // =====================

            const imageNext =
                event.target.closest(
                    ".mini-sns-image-next"
                );

            const imagePrev =
                event.target.closest(
                    ".mini-sns-image-prev"
                );


            if (
                imageNext ||
                imagePrev
            ) {

                const carousel =
                    event.target.closest(
                        ".mini-sns-carousel"
                    );

                if (!carousel) {
                    return;
                }


                const slides =
                    carousel.querySelectorAll(
                        ".mini-sns-slide"
                    );


                let current =
                    Number(
                        carousel.dataset.current
                        || 0
                    );


                if (imageNext) {

                    current =
                        Math.min(
                            current + 1,
                            slides.length - 1
                        );

                } else {

                    current =
                        Math.max(
                            current - 1,
                            0
                        );
                }


                carousel.dataset.current =
                    current;


                slides.forEach(
                    function (
                        slide,
                        index
                    ) {

                        slide.classList.toggle(
                            "active",
                            index === current
                        );

                    }
                );


                const prevButton =
                    carousel.querySelector(
                        ".mini-sns-image-prev"
                    );

                const nextButton =
                    carousel.querySelector(
                        ".mini-sns-image-next"
                    );


                if (prevButton) {

                    prevButton.hidden =
                        current === 0;
                }


                if (nextButton) {

                    nextButton.hidden =
                        current ===
                        slides.length - 1;
                }


                const counter =
                    carousel.querySelector(
                        ".mini-sns-image-current"
                    );


                if (counter) {

                    counter.textContent =
                        current + 1;
                }


                return;
            }
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

                icon.classList.toggle(
                    "liked",
                    data.liked
                );

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
                    "button, a"
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