document.addEventListener("DOMContentLoaded", () => {

    const characterNumberInput =
        document.getElementById("character_number");

    const preview =
        document.getElementById(
            "selected-character-preview"
        );

    const randomList =
        document.getElementById(
            "random-character-list"
        );

    const randomButton =
        document.querySelector(
            ".random-button"
        );

    const availableNumbersElement =
        document.getElementById(
            "available-character-numbers"
        );

    if (
        !characterNumberInput ||
        !preview ||
        !availableNumbersElement
    ) {
        return;
    }

    const availableNumbers =
        JSON.parse(
            availableNumbersElement.textContent
        );

    const availableSet =
        new Set(availableNumbers);


    function getImageUrl(number) {
        const padded =
            String(number).padStart(3, "0");

        return (
            "/static/images/characters/"
            + padded
            + ".png"
        );
    }


    function selectCharacter(number) {

        number = Number(number);

        if (!availableSet.has(number)) {

            preview.innerHTML = `
                <span>
                    この番号の画像は<br>
                    登録されていません
                </span>
            `;

            return;
        }

        characterNumberInput.value = number;

        const padded =
            String(number).padStart(3, "0");

        preview.innerHTML = `
            <img
                src="${getImageUrl(number)}"
                alt="キャラクター No.${padded}"
            >
        `;
    }


    // ==============================
    // 直接入力
    // ==============================

    characterNumberInput.addEventListener(
        "input",
        () => {

            const number =
                Number(characterNumberInput.value);

            selectCharacter(number);
        }
    );


    // ==============================
    // ランダム画像クリック
    // ==============================

    if (randomList) {

        randomList.addEventListener(
            "click",
            (event) => {

                const card =
                    event.target.closest(
                        ".character-card"
                    );

                if (!card) {
                    return;
                }

                selectCharacter(
                    card.dataset.characterNumber
                );
            }
        );
    }


    // ==============================
    // 再度ランダム
    // ==============================

    if (randomButton && randomList) {

        randomButton.addEventListener(
            "click",
            () => {

                const shuffled =
                    [...availableNumbers]
                        .sort(
                            () =>
                                Math.random() - 0.5
                        );

                const selected =
                    shuffled.slice(0, 8);

                randomList.innerHTML =
                    selected.map(
                        number => {

                            const padded =
                                String(number)
                                    .padStart(3, "0");

                            return `
                                <button
                                    type="button"
                                    class="character-card"
                                    data-character-number="${number}"
                                >
                                    <img
                                        src="${getImageUrl(number)}"
                                        alt="No.${padded}"
                                    >
                                </button>
                            `;
                        }
                    ).join("");
            }
        );
    }
});