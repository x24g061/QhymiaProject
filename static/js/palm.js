document.addEventListener(
    "DOMContentLoaded",
    function () {

        // ========================================
        // 手相レーダー
        // ========================================

        const radar =
            document.getElementById(
                "palm-radar"
            );

        const polygon =
            document.getElementById(
                "palm-radar-value"
            );


        if (
            !radar ||
            !polygon
        ) {
            return;
        }


        // ========================================
        // 属性成長ウェイト
        // ========================================

        const attributes = {

            fire:
                Number(
                    radar.dataset.fire
                ) || 0,

            water:
                Number(
                    radar.dataset.water
                ) || 0,

            grass:
                Number(
                    radar.dataset.grass
                ) || 0,

            rock:
                Number(
                    radar.dataset.rock
                ) || 0,

            light:
                Number(
                    radar.dataset.light
                ) || 0,

            dark:
                Number(
                    radar.dataset.dark
                ) || 0,

        };


        // ========================================
        // グラフ表示順
        //
        // 上：火
        // 右上：水
        // 右下：岩
        // 下：闇
        // 左下：光
        // 左上：草
        // ========================================

        const radarOrder = [
            "fire",
            "water",
            "rock",
            "dark",
            "light",
            "grass",
        ];


        // ========================================
        // 六角形の頂点
        // ========================================

        const vertices = [

            {
                x: 200,
                y: 45,
            },

            {
                x: 330,
                y: 120,
            },

            {
                x: 330,
                y: 275,
            },

            {
                x: 200,
                y: 350,
            },

            {
                x: 70,
                y: 275,
            },

            {
                x: 70,
                y: 120,
            },

        ];


        const centerX = 200;
        const centerY = 197.5;


        // ========================================
        // 成長ウェイト最大値
        // ========================================

        const MAX_GROWTH_WEIGHT = 15;


        // ========================================
        // 六角形生成
        // ========================================

        const points =
            radarOrder.map(
                function (
                    attributeName,
                    index
                ) {

                    const value =
                        attributes[
                            attributeName
                        ];


                    const ratio =
                        Math.max(
                            0,
                            Math.min(
                                value /
                                MAX_GROWTH_WEIGHT,
                                1
                            )
                        );


                    const vertex =
                        vertices[index];


                    const x =
                        centerX
                        +
                        (
                            vertex.x
                            - centerX
                        )
                        * ratio;


                    const y =
                        centerY
                        +
                        (
                            vertex.y
                            - centerY
                        )
                        * ratio;


                    return `${x},${y}`;

                }
            );


        polygon.setAttribute(
            "points",
            points.join(" ")
        );


        // ========================================
        // 最大属性を取得
        // ========================================

        const maxValue =
            Math.max(
                ...Object.values(
                    attributes
                )
            );


        const strongestAttributes =
            Object.keys(
                attributes
            ).filter(
                function (
                    attributeName
                ) {

                    return (
                        attributes[
                            attributeName
                        ]
                        ===
                        maxValue
                    );

                }
            );


        // ========================================
        // 属性カラー
        // ========================================

        const attributeColors = {

            fire: {
                fill:
                    "rgba(220, 74, 46, 0.32)",
                stroke:
                    "#d94b32",
            },

            water: {
                fill:
                    "rgba(50, 132, 201, 0.30)",
                stroke:
                    "#3284c9",
            },

            grass: {
                fill:
                    "rgba(72, 159, 92, 0.30)",
                stroke:
                    "#489f5c",
            },

            rock: {
                fill:
                    "rgba(156, 119, 67, 0.30)",
                stroke:
                    "#9c7743",
            },

            light: {
                fill:
                    "rgba(222, 176, 48, 0.30)",
                stroke:
                    "#d6a82f",
            },

            dark: {
                fill:
                    "rgba(116, 77, 170, 0.30)",
                stroke:
                    "#744daa",
            },

            neutral: {
                fill:
                    "rgba(94, 130, 140, 0.25)",
                stroke:
                    "#5e828c",
            },

        };


        // ========================================
        // 最大属性が1種類なら属性色
        // 同率ならニュートラル
        // ========================================

        let strongestAttribute =
            "neutral";


        if (
            strongestAttributes.length
            === 1
        ) {

            strongestAttribute =
                strongestAttributes[0];

        }


        const color =
            attributeColors[
                strongestAttribute
            ];


        polygon.style.fill =
            color.fill;

        polygon.style.stroke =
            color.stroke;


        // ========================================
        // 属性名の色変更
        // ========================================

        const labels =
            radar.querySelectorAll(
                ".palm-radar-svg text"
            );


        labels.forEach(
            function (
                label,
                index
            ) {

                const attributeName =
                    radarOrder[index];


                label.style.fill =
                    "#294d56";

                label.style.fontWeight =
                    "700";


                if (
                    attributeName
                    ===
                    strongestAttribute
                ) {

                    label.style.fill =
                        color.stroke;

                    label.style.fontWeight =
                        "900";

                }

            }
        );


        // ========================================
        // CSSなどで利用できるよう保存
        // ========================================

        radar.dataset.strongestAttribute =
            strongestAttribute;

    }
);