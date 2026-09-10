document.addEventListener("DOMContentLoaded", () => {

    const tabs =
        document.querySelectorAll(
            ".shop-tab"
        );

    const lists =
        document.querySelectorAll(
            ".item-list"
        );


    tabs.forEach((tab) => {

        tab.addEventListener(
            "click",
            () => {

                const category =
                    tab.dataset.category;


                // タブの選択状態を解除
                tabs.forEach(
                    (button) => {
                        button.classList.remove(
                            "active"
                        );
                    }
                );


                // 商品一覧を一度全部非表示
                lists.forEach(
                    (list) => {
                        list.classList.remove(
                            "active"
                        );
                    }
                );


                // 押したタブを選択状態にする
                tab.classList.add(
                    "active"
                );


                // 対応する商品一覧を表示
                const targetList =
                    document.querySelector(
                        `[data-list="${category}"]`
                    );


                if (targetList) {
                    targetList.classList.add(
                        "active"
                    );
                }

            }
        );

    });

});