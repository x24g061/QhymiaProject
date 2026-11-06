document.addEventListener(
    "DOMContentLoaded",
    function () {

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