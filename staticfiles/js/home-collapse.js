document.addEventListener("DOMContentLoaded", function () {

    const sections =
        document.querySelectorAll(
            ".collapsible-section"
        );


    sections.forEach(function (section) {

        const button =
            section.querySelector(
                ".collapse-toggle"
            );

        const collapseId =
            section.dataset.collapseId;


        if (!button || !collapseId) {
            return;
        }


        const heading =
            section.querySelector("h2");


        const sectionName =
            heading
                ? heading.textContent.trim()
                : "この項目";


        const storageKey =
            "qhymia-home-collapse-" +
            collapseId;


        /*
         * 状態を画面へ反映
         */

        function setCollapsed(
            isCollapsed
        ) {

            section.classList.toggle(
                "is-collapsed",
                isCollapsed
            );


            button.setAttribute(
                "aria-expanded",
                String(!isCollapsed)
            );


            button.setAttribute(
                "aria-label",
                isCollapsed
                    ? sectionName + "を開く"
                    : sectionName + "を折りたたむ"
            );

        }


        /*
         * 保存してある状態を取得
         */

        let savedState = null;


        try {

            savedState =
                localStorage.getItem(
                    storageKey
                );

        } catch (error) {

            savedState = null;

        }


        /*
         * 初期状態
         *
         * 保存がなければ開いた状態
         */

        setCollapsed(
            savedState === "collapsed"
        );


        /*
         * ボタンクリック
         */

        button.addEventListener(
            "click",
            function () {

                const isCollapsed =
                    section.classList.contains(
                        "is-collapsed"
                    );


                const nextState =
                    !isCollapsed;


                setCollapsed(
                    nextState
                );


                /*
                 * 次回アクセス時のため保存
                 */

                try {

                    localStorage.setItem(
                        storageKey,
                        nextState
                            ? "collapsed"
                            : "expanded"
                    );

                } catch (error) {

                    /*
                     * localStorageが使用できなくても
                     * 折りたたみ自体は動作させる
                     */

                }

            }
        );

    });

});