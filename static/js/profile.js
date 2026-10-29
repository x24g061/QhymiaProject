document.addEventListener(
    "DOMContentLoaded",
    function () {

        // ========================================
        // 六角形グラフ共通処理
        // ========================================

        function createRadar(
            containerId,
            polygonId,
            keys
        ) {

            const container =
                document.getElementById(
                    containerId
                );

            const polygon =
                document.getElementById(
                    polygonId
                );


            if (
                !container ||
                !polygon
            ) {
                return;
            }


            const values =
                keys.map(
                    function (key) {

                        const value =
                            Number(
                                container.dataset[
                                key
                                ]
                            );

                        return Number.isFinite(
                            value
                        )
                            ? value
                            : 0;
                    }
                );


            // ========================================
            // グラフ上限
            // ========================================

            const maxValue =
                Math.max(
                    ...values,
                    0
                );


            const chartMax =
                Math.max(
                    10,
                    Math.ceil(
                        maxValue / 10
                    ) * 10
                );


            // ========================================
            // 六角形頂点
            // ========================================

            const centerX = 200;
            const centerY = 197.5;


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


            // ========================================
            // 値を頂点位置へ変換
            // ========================================

            const points =
                values.map(
                    function (
                        value,
                        index
                    ) {

                        const ratio =
                            Math.max(
                                0,
                                Math.min(
                                    value /
                                    chartMax,
                                    1
                                )
                            );


                        const vertex =
                            vertices[
                            index
                            ];


                        const x =
                            centerX +
                            (
                                vertex.x -
                                centerX
                            ) *
                            ratio;


                        const y =
                            centerY +
                            (
                                vertex.y -
                                centerY
                            ) *
                            ratio;


                        return (
                            `${x},${y}`
                        );
                    }
                );


            polygon.setAttribute(
                "points",
                points.join(" ")
            );
        }


        // ========================================
        // 基礎ステータス
        // ========================================

        createRadar(
            "status-radar",
            "status-radar-value",
            [
                "str",
                "int",
                "agi",
                "luk",
                "vit",
                "dex",
            ]
        );


        // ========================================
        // 属性グラフ
        // ========================================

        createRadar(
            "attribute-radar",
            "attribute-radar-value",
            [
                "fire",
                "water",
                "rock",
                "dark",
                "light",
                "grass",
            ]
        );


        // ========================================
        // 最も高い属性によって
        // 六角形グラフの色を変更
        // ========================================

        const attributeRadar =
            document.getElementById(
                "attribute-radar"
            );

        const attributePolygon =
            document.getElementById(
                "attribute-radar-value"
            );


        if (
            attributeRadar &&
            attributePolygon
        ) {

            const attributes = {

                fire: Number(
                    attributeRadar.dataset.fire
                ) || 0,

                water: Number(
                    attributeRadar.dataset.water
                ) || 0,

                grass: Number(
                    attributeRadar.dataset.grass
                ) || 0,

                rock: Number(
                    attributeRadar.dataset.rock
                ) || 0,

                light: Number(
                    attributeRadar.dataset.light
                ) || 0,

                dark: Number(
                    attributeRadar.dataset.dark
                ) || 0,

            };


            // ====================================
            // 最大属性値
            // ====================================

            const maxAttributeValue =
                Math.max(
                    ...Object.values(
                        attributes
                    )
                );


            // ====================================
            // 最大値の属性を取得
            // ====================================

            const strongestAttributes =
                Object.keys(
                    attributes
                ).filter(
                    function (attribute) {

                        return (
                            attributes[
                            attribute
                            ] ===
                            maxAttributeValue
                        );
                    }
                );


            // ====================================
            // 属性カラー
            // ====================================

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


            // ====================================
            // 一番高い属性が1つならその色
            //
            // 同率ならneutral
            // ====================================

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


            attributePolygon.style.fill =
                color.fill;

            attributePolygon.style.stroke =
                color.stroke;

            // ====================================
            // 最大属性の文字色も変更
            // ====================================

            const attributeLabels =
                attributeRadar.querySelectorAll(
                    ".profile-radar-svg text"
                );


            const labelAttributeOrder = [
                "fire",
                "water",
                "rock",
                "dark",
                "light",
                "grass",
            ];


            attributeLabels.forEach(
                function (
                    label,
                    index
                ) {

                    const attributeName =
                        labelAttributeOrder[
                        index
                        ];


                    // まず通常色に戻す
                    label.style.fill =
                        "#294d56";


                    // 最大属性だけ色変更
                    if (
                        attributeName ===
                        strongestAttribute
                    ) {

                        label.style.fill =
                            color.stroke;

                        label.style.fontWeight =
                            "900";
                    }

                }
            );

            // 属性グラフ全体にも属性名を保存
            attributeRadar.dataset.strongestAttribute =
                strongestAttribute;
        }

    }
);