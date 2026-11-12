
/* =========================================
   Qhymia ゲーム表示設定
========================================= */

(() => {
    "use strict";

    const THEME_KEY = "qhymia_game_theme";
    const FONT_KEY = "qhymia_game_font";

    const validThemes = ["light", "dark"];
    const validFonts = ["standard", "mincho", "rounded"];

    // ========================================
    // 保存済み設定の読み込み
    // ========================================

    function readSetting(key, fallback, allowed) {
        try {
            const value = localStorage.getItem(key);

            return allowed.includes(value)
                ? value
                : fallback;

        } catch {
            return fallback;
        }
    }

    // ========================================
    // 設定の保存
    // ========================================

    function saveSetting(key, value) {
        try {
            localStorage.setItem(key, value);
        } catch {
            // 保存できない場合も画面切り替えは有効
        }
    }

    // ========================================
    // ダークモード切り替え
    // ========================================

    function applyTheme(theme) {
        if (!validThemes.includes(theme)) {
            return;
        }

        document.documentElement.dataset.gameTheme = theme;

        saveSetting(THEME_KEY, theme);
    }

    // ========================================
    // フォント切り替え
    // ========================================

    function applyFont(font) {
        if (!validFonts.includes(font)) {
            return;
        }

        document.documentElement.dataset.gameFont = font;

        saveSetting(FONT_KEY, font);
    }

    // ========================================
    // 保存済み設定を復元
    // ========================================

    const currentTheme = readSetting(
        THEME_KEY,
        "light",
        validThemes
    );

    const currentFont = readSetting(
        FONT_KEY,
        "standard",
        validFonts
    );

    applyTheme(currentTheme);
    applyFont(currentFont);

    // ========================================
    // 設定画面の操作
    // ========================================

    document.addEventListener("DOMContentLoaded", () => {

        const themeSelect = document.getElementById(
            "game-theme"
        );

        const fontSelect = document.getElementById(
            "game-font"
        );

        const resetButton = document.getElementById(
            "game-settings-reset"
        );

        // 画面テーマ
        if (themeSelect) {

            themeSelect.value = currentTheme;

            themeSelect.addEventListener("change", () => {
                applyTheme(themeSelect.value);
            });
        }

        // フォント
        if (fontSelect) {

            fontSelect.value = currentFont;

            fontSelect.addEventListener("change", () => {
                applyFont(fontSelect.value);
            });
        }

        // 初期設定に戻す
        if (resetButton) {

            resetButton.addEventListener("click", () => {

                applyTheme("light");
                applyFont("standard");

                if (themeSelect) {
                    themeSelect.value = "light";
                }

                if (fontSelect) {
                    fontSelect.value = "standard";
                }
            });
        }

    });

})();
