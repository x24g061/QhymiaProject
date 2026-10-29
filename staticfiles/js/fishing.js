(() => {
    "use strict";

    const startButton = document.getElementById("fishing-start");
    const holdButton = document.getElementById("fishing-hold");

    if (!startButton || !holdButton) return;

    const message = document.getElementById("fishing-message");
    const scene = document.getElementById("fishing-scene");
    const sceneLabel = document.getElementById("scene-label");
    const fish = document.getElementById("fishing-fish");
    const catchBar = document.getElementById("catch-progress");
    const tensionBar = document.getElementById("tension-progress");
    const catchValue = document.getElementById("catch-value");
    const tensionValue = document.getElementById("tension-value");
    const fishState = document.getElementById("fish-state");
    const timeValue = document.getElementById("time-value");
    const result = document.getElementById("fishing-result");

    const RARITIES = [
        {
            name: "コモン",
            probability: 60,
            timeLimit: 40,
            pullSpeed: 19,
            wildPullSpeed: 5,
            tensionUp: 10,
            wildTensionUp: 28,
            tensionDown: 45,
            wildDuration: [1, 1.6],
            calmDuration: [2.5, 4],
        },
        {
            name: "レア",
            probability: 25,
            timeLimit: 35,
            pullSpeed: 16,
            wildPullSpeed: 3,
            tensionUp: 13,
            wildTensionUp: 38,
            tensionDown: 38,
            wildDuration: [1.3, 2],
            calmDuration: [2, 3],
        },
        {
            name: "エピック",
            probability: 12,
            timeLimit: 35,
            pullSpeed: 13,
            wildPullSpeed: 2,
            tensionUp: 17,
            wildTensionUp: 46,
            tensionDown: 35,
            wildDuration: [1.5, 2.4],
            calmDuration: [1.5, 2.5],
        },
        {
            name: "レジェンド",
            probability: 3,
            timeLimit: 40,
            pullSpeed: 11,
            wildPullSpeed: 1,
            tensionUp: 20,
            wildTensionUp: 55,
            tensionDown: 33,
            wildDuration: [1.8, 2.7],
            calmDuration: [1.2, 2],
        },
    ];

    let currentRarity = RARITIES[0];

    function chooseRarity() {
        const roll = Math.random() * 100;
        let total = 0;

        for (const rarity of RARITIES) {
            total += rarity.probability;

            if (roll < total) {
                return rarity;
            }
        }

        return RARITIES[0];
    }

    let phase = "idle";
    let progress = 0;
    let tension = 0;
    let remaining = currentRarity.timeLimit;
    let wild = false;
    let behaviorRemaining = 0;
    let lastTime = 0;
    let frameId = null;
    let biteTimer = null;
    let pointerId = null;
    let keyboardHeld = false;

    const random = (min, max) => min + Math.random() * (max - min);
    const isHolding = () => pointerId !== null || keyboardHeld;

    function render() {
        catchBar.value = progress;
        tensionBar.value = tension;

        catchValue.textContent = `${Math.floor(progress)}%`;
        tensionValue.textContent = `${Math.floor(tension)}%`;
        timeValue.textContent = `${Math.max(0, Math.ceil(remaining))}秒`;

        tensionBar.classList.toggle("is-danger", tension >= 75);
        holdButton.classList.toggle("is-holding", isHolding());
        holdButton.textContent = isHolding()
            ? "引き寄せ中！ 離すと緩める"
            : "長押しで引く";

        fish.style.left = `${75 - progress * 0.46}%`;
    }

    function releaseInput() {
        const capturedPointer = pointerId;
        pointerId = null;
        keyboardHeld = false;

        if (
            capturedPointer !== null &&
            holdButton.hasPointerCapture(capturedPointer)
        ) {
            holdButton.releasePointerCapture(capturedPointer);
        }

        render();
    }

    function setBehavior(nextWild) {
        wild = nextWild;

        behaviorRemaining = wild
            ? random(...currentRarity.wildDuration)
            : random(...currentRarity.calmDuration);

        scene.classList.toggle("is-wild", wild);

        fishState.textContent = wild
            ? `魚：${currentRarity.name}（暴れている！）`
            : `魚：${currentRarity.name}（落ち着いている）`;

        sceneLabel.textContent = wild
            ? "水しぶき！ 糸を緩めよう"
            : "今が引き寄せるチャンス";

        message.textContent = wild
            ? "魚が暴れている！ 指を離してテンションを下げよう。"
            : "魚が落ち着いた！ 長押しで引き寄せよう。";
    }

    function finish(success, reason = "") {
        phase = "finished";

        clearTimeout(biteTimer);
        cancelAnimationFrame(frameId);
        biteTimer = null;
        frameId = null;

        releaseInput();

        scene.classList.remove("is-fighting", "is-wild");
        holdButton.disabled = true;
        startButton.disabled = false;
        startButton.textContent = "もう一度釣る";

        result.hidden = false;
        result.classList.toggle("is-failure", !success);

        if (success) {
            const size = random(15, 40).toFixed(1);

            result.textContent =
                `釣り成功！【${currentRarity.name}】湖の魚（${size}cm）を釣り上げた！`;

            message.textContent = "お見事！ 魚を釣り上げました。";
            sceneLabel.textContent = "釣り成功！";

        } else {
            result.textContent = reason;
            message.textContent = "惜しい！ もう一度挑戦してみよう。";
            sceneLabel.textContent = "魚が逃げていった……";
        }

        fishState.textContent = "魚：釣り終了";
    }

    function update(now) {
        if (phase !== "fighting") return;

        // 長時間画面を離れた場合は visibilitychange 側で終了する。
        const dt = Math.min((now - lastTime) / 1000, 0.1);
        lastTime = now;

        remaining = Math.max(0, remaining - dt);
        behaviorRemaining -= dt;

        if (behaviorRemaining <= 0) {
            setBehavior(!wild);
        }

        if (isHolding()) {
            progress += (
                wild
                    ? currentRarity.wildPullSpeed
                    : currentRarity.pullSpeed
            ) * dt;

            tension += (
                wild
                    ? currentRarity.wildTensionUp
                    : currentRarity.tensionUp
            ) * dt;

        } else {
            progress -= (wild ? 5 : 2) * dt;
            tension -= currentRarity.tensionDown * dt;
        }

        progress = Math.max(0, Math.min(100, progress));
        tension = Math.max(0, Math.min(100, tension));

        render();

        if (tension >= 100) {
            finish(false, "糸が切れてしまった！ 暴れている間は指を離そう。");
            return;
        }

        if (progress >= 100) {
            finish(true);
            return;
        }

        if (remaining <= 0) {
            finish(false, "時間切れ！ 魚に逃げられてしまった。");
            return;
        }

        frameId = requestAnimationFrame(update);
    }

    function startFishing() {
        if (phase === "waiting" || phase === "fighting") return;

        releaseInput();

        phase = "waiting";
        progress = 0;
        tension = 0;
        currentRarity = chooseRarity();
        remaining = currentRarity.timeLimit;
        result.hidden = true;
        result.classList.remove("is-failure");

        startButton.disabled = true;
        startButton.textContent = "魚を待っています…";
        holdButton.disabled = true;

        scene.classList.remove("is-fighting", "is-wild");
        message.textContent = "糸を投げた……魚が食いつくのを待とう。";
        sceneLabel.textContent = "浮きが揺れている……";
        fishState.textContent = "魚：まだかかっていません";

        render();
        timeValue.textContent = "—";

        biteTimer = window.setTimeout(() => {
            if (phase !== "waiting") return;

            biteTimer = null;
            phase = "fighting";

            holdButton.disabled = false;
            startButton.textContent = "釣り中";
            scene.classList.add("is-fighting");

            setBehavior(false);
            sceneLabel.textContent =
                `${currentRarity.name}の魚が食いついた！`;

            message.textContent =
                `【${currentRarity.name}】魚が食いついた！ 長押しで引き寄せよう。`;
            lastTime = performance.now();
            render();

            frameId = requestAnimationFrame(update);
        }, random(1500, 3000));
    }

    startButton.addEventListener("click", startFishing);

    holdButton.addEventListener("pointerdown", (event) => {
        if (phase !== "fighting") return;
        if (!event.isPrimary || event.button !== 0) return;
        if (pointerId !== null) return;

        event.preventDefault();

        pointerId = event.pointerId;
        holdButton.setPointerCapture(event.pointerId);
        render();
    });

    function releasePointer(event) {
        if (event.pointerId !== pointerId) return;

        pointerId = null;

        if (holdButton.hasPointerCapture(event.pointerId)) {
            holdButton.releasePointerCapture(event.pointerId);
        }

        render();
    }

    holdButton.addEventListener("pointerup", releasePointer);
    holdButton.addEventListener("pointercancel", releasePointer);
    holdButton.addEventListener("lostpointercapture", releasePointer);

    holdButton.addEventListener("contextmenu", (event) => {
        event.preventDefault();
    });

    document.addEventListener("keydown", (event) => {
        if (event.code !== "Space" || phase !== "fighting") return;

        const target = event.target;
        const editing = target instanceof HTMLElement && (
            target.isContentEditable ||
            target.closest("input, textarea, select")
        );

        if (editing || event.ctrlKey || event.altKey || event.metaKey) return;

        // 別のリンクやボタンの操作は妨げない。
        if (
            target instanceof HTMLElement &&
            target.closest("a, button") &&
            target !== holdButton &&
            target !== startButton
        ) return;

        event.preventDefault();
        keyboardHeld = true;
        render();
    });

    document.addEventListener("keyup", (event) => {
        if (event.code !== "Space") return;

        keyboardHeld = false;
        render();
    });

    window.addEventListener("blur", releaseInput);

    document.addEventListener("visibilitychange", () => {
        if (!document.hidden) return;

        releaseInput();

        if (phase === "waiting" || phase === "fighting") {
            finish(false, "画面を離れたため、釣りを終了しました。");
        }
    });

    window.addEventListener("pagehide", () => {
        clearTimeout(biteTimer);
        cancelAnimationFrame(frameId);
        releaseInput();

        if (phase === "waiting" || phase === "fighting") {
            finish(false, "ページを離れたため、釣りを終了しました。");
        }
    });
})();