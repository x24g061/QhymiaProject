document.addEventListener("DOMContentLoaded", () => {

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


    let currentCategory =
        "all";



    /*
     * 商品取得
     */
    function getItems() {

        return Array.from(
            document.querySelectorAll(
                "[data-item]"
            )
        );

    }



    /*
     * 絞り込み
     */
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



    /*
     * カテゴリー切り替え
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
                    currentCategory === "all"
                ) {

                    categoryTitle.textContent =
                        "販売中のアイテム";

                }

                else {

                    categoryTitle.textContent =
                        `${button.textContent.trim()}の商品`;

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


    filterItems();

});