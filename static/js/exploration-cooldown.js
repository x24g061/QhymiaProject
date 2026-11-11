document.addEventListener(
    "DOMContentLoaded",
    function () {

        // 選択階層をキャラクターごとに記憶する。
        // CT終了時の自動再読み込みでも選択が戻らないようにする。
        const floorSelect = document.getElementById("exploration-floor");

        if (floorSelect) {
            const key = "qhymia:exploration-floor:" + floorSelect.dataset.characterId;

            try {
                const savedFloor = localStorage.getItem(key);
                if (savedFloor !== null) {
                    const available = Array.from(floorSelect.options).some(
                        (option) => option.value === savedFloor && !option.disabled
                    );
                    if (available) {
                        floorSelect.value = savedFloor;
                    } else {
                        localStorage.removeItem(key);
                    }
                }

                const rememberFloor = () => localStorage.setItem(key, floorSelect.value);
                floorSelect.addEventListener("change", rememberFloor);

                // 選択後に即送信された場合にも保存する。
                const form = floorSelect.closest("form");
                if (form) {
                    form.addEventListener("submit", rememberFloor);
                }
            } catch (error) {
                // ストレージ制限下でも探索操作自体は続行できる。
            }
        }

        const button =
            document.getElementById(
                "exploration-cooldown-button"
            );


        const secondsElements =
            document.querySelectorAll(
                ".js-cooldown-seconds"
            );


        if (
            !button ||
            secondsElements.length === 0
        ) {
            return;
        }


        const initialRemaining =
            Number(
                button.dataset.remaining
            );


        if (
            !Number.isFinite(
                initialRemaining
            ) ||
            initialRemaining <= 0
        ) {
            return;
        }


        /*
         * ページを開いた時点から
         * クールタイム終了時刻を作る。
         *
         * 単純に remaining -= 1 ではなく
         * 現在時刻との差から計算するため、
         * スマホや別タブでJSが一時停止しても
         * 実際のクールタイムとズレにくい。
         */
        const endTime =
            Date.now()
            +
            initialRemaining * 1000;


        function updateCooldown() {

            const remaining =
                Math.max(
                    0,
                    Math.ceil(
                        (
                            endTime
                            -
                            Date.now()
                        )
                        /
                        1000
                    )
                );


            secondsElements.forEach(
                function (element) {

                    element.textContent =
                        remaining;

                }
            );


            if (remaining <= 0) {

                window.location.reload();

                return false;
            }


            return true;
        }


        updateCooldown();


        const timer =
            setInterval(
                function () {

                    const running =
                        updateCooldown();


                    if (!running) {

                        clearInterval(
                            timer
                        );

                    }

                },
                250
            );

    }
);
