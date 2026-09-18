document.addEventListener("DOMContentLoaded", () => {

    /*
     * 左メニュー切り替え
     */

    const sideButtons =
        document.querySelectorAll(
            ".side-button[data-target]"
        );


    const equipmentPanel =
        document.querySelector(
            "#equipment-panel"
        );


    const itemsPanel =
        document.querySelector(
            "#items-panel"
        );


    sideButtons.forEach(button => {

        button.addEventListener(
            "click",
            () => {

                sideButtons.forEach(target => {

                    target.classList.remove(
                        "active"
                    );

                });


                button.classList.add(
                    "active"
                );


                equipmentPanel.classList.remove(
                    "active-panel"
                );

                itemsPanel.classList.remove(
                    "active-panel"
                );


                if (
                    button.dataset.target ===
                    "equipment"
                ) {

                    equipmentPanel.classList.add(
                        "active-panel"
                    );

                }

                else {

                    itemsPanel.classList.add(
                        "active-panel"
                    );

                }

            }
        );

    });



    /*
     * 所持アイテム
     */

    const itemList =
        document.querySelector(
            "#items"
        );


    const searchInput =
        document.querySelector(
            "#search"
        );


    const sortSelect =
        document.querySelector(
            "#sort"
        );


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


    let currentCategory =
        "all";


    function getItems() {

        return Array.from(
            document.querySelectorAll(
                "[data-item]"
            )
        );

    }


    function filterItems() {

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
                name.includes(
                    keyword
                );


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



    /*
     * カテゴリ
     */

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


                if (
                    currentCategory ===
                    "all"
                ) {

                    categoryTitle.textContent =
                        "所持アイテム";

                }

                else {

                    categoryTitle.textContent =
                        `${button.textContent.trim()}一覧`;

                }


                filterItems();

            }
        );

    });



    /*
     * 検索
     */

    searchInput.addEventListener(
        "input",
        filterItems
    );



    /*
     * 並び替え
     */

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


            else if (
                type === "quantity-high"
            ) {

                sorted.sort(
                    (a, b) =>
                        Number(
                            b.dataset.quantity
                        ) -
                        Number(
                            a.dataset.quantity
                        )
                );

            }


            else if (
                type === "quantity-low"
            ) {

                sorted.sort(
                    (a, b) =>
                        Number(
                            a.dataset.quantity
                        ) -
                        Number(
                            b.dataset.quantity
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


    filterItems();

});