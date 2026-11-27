document.addEventListener("DOMContentLoaded", () => {

    // ========================================================
    // 販売中アイテム一覧
    // ========================================================

    const itemList =
        document.querySelector("#items");

    const searchInput =
        document.querySelector("#search");

    const sortSelect =
        document.querySelector("#sort");

    const categoryButtons =
        document.querySelectorAll(
            ".category-button"
        );

    const categoryTitle =
        document.querySelector(
            "#category-title"
        );

    const searchEmpty =
        document.querySelector(
            "#search-empty"
        );


    // ========================================================
    // 左メニュー / パネル切り替え
    // ========================================================

    const listingTabButton =
        document.querySelector(
            "#listing-tab-button"
        );

    const inventoryTabButton =
        document.querySelector(
            "#inventory-tab-button"
        );

    const listingPanel =
        document.querySelector(
            "#listing-panel"
        );

    const inventoryPanel =
        document.querySelector(
            "#inventory-panel"
        );

    const equipmentTabButton =
        document.querySelector(
            "#equipment-tab-button"
        );

    const equipmentPanel =
        document.querySelector(
            "#equipment-panel"
        );


    let currentCategory =
        "all";


    // ========================================================
    // 販売中アイテム取得
    // ========================================================

    function getItems() {

        return Array.from(
            document.querySelectorAll(
                "[data-item]"
            )
        );

    }


    // ========================================================
    // 絞り込み
    // ========================================================

    function filterItems() {

        // 販売一覧が存在しない場合は何もしない
        if (
            !searchInput ||
            !searchEmpty
        ) {
            return;
        }


        const items =
            getItems();

        const keyword =
            searchInput.value
                .trim()
                .toLowerCase();


        let visibleCount =
            0;


        items.forEach(item => {

            const name =
                item.dataset.name
                    .toLowerCase();

            const category =
                item.dataset.category;


            const keywordMatch =
                name.includes(keyword);


            const categoryMatch =
                currentCategory === "all" ||
                category === currentCategory;


            if (
                keywordMatch &&
                categoryMatch
            ) {

                item.style.display =
                    "";

                visibleCount++;

            }

            else {

                item.style.display =
                    "none";

            }

        });


        if (
            items.length > 0 &&
            visibleCount === 0
        ) {

            searchEmpty.classList.remove(
                "hidden"
            );

        }

        else {

            searchEmpty.classList.add(
                "hidden"
            );

        }

    }


    // ========================================================
    // カテゴリー切り替え
    // ========================================================

    categoryButtons.forEach(button => {

        button.addEventListener(
            "click",
            () => {

                categoryButtons.forEach(
                    target => {

                        target.classList.remove(
                            "active"
                        );

                    }
                );


                button.classList.add(
                    "active"
                );


                currentCategory =
                    button.dataset.category;


                if (categoryTitle) {

                    if (
                        currentCategory === "all"
                    ) {

                        categoryTitle.textContent =
                            "販売中のアイテム";

                    }

                    else {

                        categoryTitle.textContent =
                            `${button.textContent.trim()}の商品`;

                    }

                }


                filterItems();

            }
        );

    });


    // ========================================================
    // 検索
    // ========================================================

    if (searchInput) {

        searchInput.addEventListener(
            "input",
            filterItems
        );

    }


    // ========================================================
    // 並び替え
    // ========================================================

    if (
        sortSelect &&
        itemList
    ) {

        sortSelect.addEventListener(
            "change",
            () => {

                const items =
                    getItems();

                const type =
                    sortSelect.value;


                const sorted =
                    [...items];


                if (
                    type === "price-low"
                ) {

                    sorted.sort(
                        (a, b) =>
                            Number(
                                a.dataset.price
                            ) -
                            Number(
                                b.dataset.price
                            )
                    );

                }


                else if (
                    type === "price-high"
                ) {

                    sorted.sort(
                        (a, b) =>
                            Number(
                                b.dataset.price
                            ) -
                            Number(
                                a.dataset.price
                            )
                    );

                }


                else if (
                    type === "name"
                ) {

                    sorted.sort(
                        (a, b) =>
                            a.dataset.name.localeCompare(
                                b.dataset.name,
                                "ja"
                            )
                    );

                }


                sorted.forEach(item => {

                    itemList.appendChild(
                        item
                    );

                });


                filterItems();

            }
        );

    }


    // ========================================================
    // 左メニュー
    // 出品中のアイテムを表示
    // ========================================================

    if (
        listingTabButton &&
        inventoryTabButton &&
        equipmentTabButton &&
        listingPanel &&
        inventoryPanel &&
        equipmentPanel
    ) {

        listingTabButton.addEventListener(
            "click",
            () => {

                listingPanel.style.display =
                    "";

                inventoryPanel.style.display =
                    "none";

                equipmentPanel.style.display =
                    "none";


                listingTabButton.classList.add(
                    "active"
                );

                inventoryTabButton.classList.remove(
                    "active"
                );

                equipmentTabButton.classList.remove(
                    "active"
                );

            }
        );

        // ====================================================
        // 手持ちのアイテムを表示
        // ====================================================

        inventoryTabButton.addEventListener(
            "click",
            () => {

                listingPanel.style.display =
                    "none";

                inventoryPanel.style.display =
                    "";

                equipmentPanel.style.display =
                    "none";


                inventoryTabButton.classList.add(
                    "active"
                );

                listingTabButton.classList.remove(
                    "active"
                );

                equipmentTabButton.classList.remove(
                    "active"
                );

            }
        );


        equipmentTabButton.addEventListener(
            "click",
            () => {

                listingPanel.style.display =
                    "none";

                inventoryPanel.style.display =
                    "none";

                equipmentPanel.style.display =
                    "";


                equipmentTabButton.classList.add(
                    "active"
                );

                listingTabButton.classList.remove(
                    "active"
                );

                inventoryTabButton.classList.remove(
                    "active"
                );

            }
        );
    }

    // ========================================================
    // NPCショップ
    // 左メニュー / パネル切り替え
    // ========================================================

    const npcShopTabButtons =
        document.querySelectorAll(
            ".npc-shop-tab-button"
        );

    const npcShopPanels =
        document.querySelectorAll(
            ".npc-shop-panel"
        );


    if (
        npcShopTabButtons.length > 0 &&
        npcShopPanels.length > 0
    ) {

        npcShopTabButtons.forEach(button => {

            button.addEventListener(
                "click",
                () => {

                    // ボタンのactiveを全部外す
                    npcShopTabButtons.forEach(target => {
                        target.classList.remove("active");
                    });


                    // パネルを全部非表示状態にする
                    npcShopPanels.forEach(panel => {
                        panel.classList.remove("active");
                    });


                    // 押したボタンをactiveにする
                    button.classList.add("active");


                    // 表示対象ID取得
                    const panelId =
                        button.dataset.npcPanel;


                    // 対象パネル取得
                    const panel =
                        document.getElementById(
                            panelId
                        );


                    // 対象だけ表示
                    if (panel) {
                        panel.classList.add("active");
                    }

                }
            );

        });

    }

    // ========================================================
// NPCショップ
// 数量 +/- / 合計金額
// ========================================================

const npcQuantityControls =
    document.querySelectorAll(
        ".npc-quantity-control"
    );


npcQuantityControls.forEach(control => {

    const input =
        control.querySelector(
            ".npc-quantity-input"
        );

    const minusButton =
        control.querySelector(
            ".npc-quantity-minus"
        );

    const plusButton =
        control.querySelector(
            ".npc-quantity-plus"
        );

    const row =
        control.closest(
            "[data-item]"
        );


    if (
        !input ||
        !minusButton ||
        !plusButton ||
        !row
    ) {
        return;
    }


    const totalPrice =
        row.querySelector(
            ".npc-total-price"
        );


    const min =
        Number(
            input.min || 1
        );

    const max =
        Number(
            input.max || 1
        );

    const unitPrice =
        Number(
            row.dataset.price || 0
        );


    function normalizeQuantity() {

        let value =
            Number(
                input.value
            );


        if (
            !Number.isFinite(value) ||
            value < min
        ) {
            value = min;
        }


        if (value > max) {
            value = max;
        }


        value =
            Math.floor(
                value
            );


        input.value =
            value;


        return value;

    }


function updateQuantityUI() {

    const quantity =
        normalizeQuantity();


    const total =
        unitPrice * quantity;


    if (totalPrice) {

        totalPrice.textContent =
            `合計 ${total.toLocaleString()} Q`;

    }


    minusButton.disabled =
        quantity <= min;

    plusButton.disabled =
        quantity >= max;


    const characterGold =
        Number(
            row.dataset.characterGold || 0
        );


    const buyButton =
        row.querySelector(
            ".buy-button"
        );


    if (buyButton) {

        if (total > characterGold) {

            buyButton.disabled = true;

            buyButton.classList.add(
                "insufficient-q"
            );

            buyButton.textContent =
                "Q不足";

        }

        else {

            buyButton.disabled = false;

            buyButton.classList.remove(
                "insufficient-q"
            );

            buyButton.textContent =
                "購入する";

        }

    }

}


    minusButton.addEventListener(
        "click",
        () => {

            input.value =
                normalizeQuantity() - 1;

            updateQuantityUI();

        }
    );


    plusButton.addEventListener(
        "click",
        () => {

            input.value =
                normalizeQuantity() + 1;

            updateQuantityUI();

        }
    );


    input.addEventListener(
        "input",
        updateQuantityUI
    );


    input.addEventListener(
        "change",
        updateQuantityUI
    );


    updateQuantityUI();

});

// ========================================================
// NPCショップ
// 購入確認モーダル
// ========================================================

const npcPurchaseModal =
    document.querySelector(
        "#npc-purchase-modal"
    );

const npcModalItemName =
    document.querySelector(
        "#npc-modal-item-name"
    );

const npcModalQuantity =
    document.querySelector(
        "#npc-modal-quantity"
    );

const npcModalTotal =
    document.querySelector(
        "#npc-modal-total"
    );

const npcModalCancel =
    document.querySelector(
        "#npc-modal-cancel"
    );

const npcModalConfirm =
    document.querySelector(
        "#npc-modal-confirm"
    );


let pendingNpcPurchaseForm =
    null;


document.querySelectorAll(
    ".buy-button"
).forEach(button => {

    button.addEventListener(
        "click",
        event => {

            // Q不足・売り切れなどで無効化されている場合
            if (button.disabled) {
                return;
            }


            const form =
                button.closest(
                    "form"
                );


            const row =
                button.closest(
                    "[data-item]"
                );


            if (
                !form ||
                !row ||
                !npcPurchaseModal
            ) {
                return;
            }


            event.preventDefault();


            const input =
                row.querySelector(
                    ".npc-quantity-input"
                );


            const quantity =
                Number(
                    input?.value || 1
                );


            const price =
                Number(
                    row.dataset.price || 0
                );


            const total =
                price * quantity;


            pendingNpcPurchaseForm =
                form;


            if (npcModalItemName) {

                npcModalItemName.textContent =
                    button.dataset.itemName || "商品";

            }


            if (npcModalQuantity) {

                npcModalQuantity.textContent =
                    `数量：${quantity}個`;

            }


            if (npcModalTotal) {

                npcModalTotal.textContent =
                    `合計：${total.toLocaleString()} Q`;

            }


            npcPurchaseModal.classList.add(
                "active"
            );

        }
    );

});


if (npcModalCancel) {

    npcModalCancel.addEventListener(
        "click",
        () => {

            npcPurchaseModal?.classList.remove(
                "active"
            );


            pendingNpcPurchaseForm =
                null;

        }
    );

}


if (npcModalConfirm) {

    npcModalConfirm.addEventListener(
        "click",
        () => {

            if (!pendingNpcPurchaseForm) {
                return;
            }


            const form =
                pendingNpcPurchaseForm;


            pendingNpcPurchaseForm =
                null;


            npcPurchaseModal?.classList.remove(
                "active"
            );


            form.submit();

        }
    );

}


// モーダル外をクリックしたら閉じる
if (npcPurchaseModal) {

    npcPurchaseModal.addEventListener(
        "click",
        event => {

            if (
                event.target ===
                npcPurchaseModal
            ) {

                npcPurchaseModal.classList.remove(
                    "active"
                );


                pendingNpcPurchaseForm =
                    null;

            }

        }
    );

}

// ========================================================
// フリーマーケット
// 数量 +/- / 合計金額 / Q不足判定
// ========================================================

const marketQuantityControls =
    document.querySelectorAll(
        ".market-quantity-control"
    );


marketQuantityControls.forEach(control => {

    const input =
        control.querySelector(
            ".market-buy-quantity-input"
        );

    const minusButton =
        control.querySelector(
            ".market-quantity-minus"
        );

    const plusButton =
        control.querySelector(
            ".market-quantity-plus"
        );

    const row =
        control.closest(
            "[data-item]"
        );


    if (
        !input ||
        !minusButton ||
        !plusButton ||
        !row
    ) {
        return;
    }


    const totalPrice =
        row.querySelector(
            ".market-total-price"
        );


    const buyButton =
        row.querySelector(
            ".buy-button"
        );


    const min =
        Number(
            input.min || 1
        );


    const max =
        Number(
            input.max || 1
        );


    const unitPrice =
        Number(
            row.dataset.price || 0
        );


    const characterGold =
        Number(
            row.dataset.characterGold || 0
        );


    function normalizeMarketQuantity() {

        let value =
            Number(
                input.value
            );


        if (
            !Number.isFinite(value) ||
            value < min
        ) {
            value = min;
        }


        if (value > max) {
            value = max;
        }


        value =
            Math.floor(
                value
            );


        input.value =
            value;


        return value;

    }


    function updateMarketQuantityUI() {

        const quantity =
            normalizeMarketQuantity();


        const total =
            unitPrice * quantity;


        if (totalPrice) {

            totalPrice.textContent =
                `合計 ${total.toLocaleString()} Q`;

        }


        minusButton.disabled =
            quantity <= min;


        plusButton.disabled =
            quantity >= max;


        if (buyButton) {

            if (total > characterGold) {

                buyButton.disabled =
                    true;


                buyButton.classList.add(
                    "insufficient-q"
                );


                buyButton.textContent =
                    "Q不足";

            }

            else {

                buyButton.disabled =
                    false;


                buyButton.classList.remove(
                    "insufficient-q"
                );


                buyButton.textContent =
                    "購入する";

            }

        }

    }


    minusButton.addEventListener(
        "click",
        () => {

            input.value =
                normalizeMarketQuantity() - 1;


            updateMarketQuantityUI();

        }
    );


    plusButton.addEventListener(
        "click",
        () => {

            input.value =
                normalizeMarketQuantity() + 1;


            updateMarketQuantityUI();

        }
    );


    input.addEventListener(
        "input",
        updateMarketQuantityUI
    );


    input.addEventListener(
        "change",
        updateMarketQuantityUI
    );


    updateMarketQuantityUI();

});
// ========================================================
// フリーマーケット
// 購入確認モーダル
// ========================================================

const marketPurchaseModal =
    document.querySelector(
        "#market-purchase-modal"
    );

const marketModalItemName =
    document.querySelector(
        "#market-modal-item-name"
    );

const marketModalQuantity =
    document.querySelector(
        "#market-modal-quantity"
    );

const marketModalTotal =
    document.querySelector(
        "#market-modal-total"
    );

const marketModalCancel =
    document.querySelector(
        "#market-modal-cancel"
    );

const marketModalConfirm =
    document.querySelector(
        "#market-modal-confirm"
    );


let pendingMarketPurchaseForm =
    null;


document.querySelectorAll(
    ".market-buy-button"
).forEach(button => {

    button.addEventListener(
        "click",
        event => {

            if (button.disabled) {
                return;
            }


            const form =
                button.closest(
                    "form"
                );


            const row =
                button.closest(
                    "[data-item]"
                );


            if (
                !form ||
                !row ||
                !marketPurchaseModal
            ) {
                return;
            }


            event.preventDefault();


            const quantityInput =
                row.querySelector(
                    ".market-buy-quantity-input"
                );


            const quantity =
                quantityInput
                    ? Number(quantityInput.value || 1)
                    : 1;


            const price =
                Number(
                    row.dataset.price || 0
                );


            const total =
                price * quantity;


            pendingMarketPurchaseForm =
                form;


            if (marketModalItemName) {

                marketModalItemName.textContent =
                    button.dataset.itemName || "商品";

            }


            if (marketModalQuantity) {

                marketModalQuantity.textContent =
                    `数量：${quantity}個`;

            }


            if (marketModalTotal) {

                marketModalTotal.textContent =
                    `合計：${total.toLocaleString()} Q`;

            }


            marketPurchaseModal.classList.add(
                "active"
            );

        }
    );

});


if (marketModalCancel) {

    marketModalCancel.addEventListener(
        "click",
        () => {

            marketPurchaseModal?.classList.remove(
                "active"
            );


            pendingMarketPurchaseForm =
                null;

        }
    );

}


if (marketModalConfirm) {

    marketModalConfirm.addEventListener(
        "click",
        () => {

            if (!pendingMarketPurchaseForm) {
                return;
            }


            const form =
                pendingMarketPurchaseForm;


            pendingMarketPurchaseForm =
                null;


            marketPurchaseModal?.classList.remove(
                "active"
            );


            form.submit();

        }
    );

}


// モーダル外をクリックしたら閉じる
if (marketPurchaseModal) {

    marketPurchaseModal.addEventListener(
        "click",
        event => {

            if (
                event.target ===
                marketPurchaseModal
            ) {

                marketPurchaseModal.classList.remove(
                    "active"
                );


                pendingMarketPurchaseForm =
                    null;

            }

        }
    );

}
    // ========================================================
    // 初期表示
    // ========================================================

    filterItems();

});