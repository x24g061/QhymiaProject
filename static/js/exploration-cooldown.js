document.addEventListener("DOMContentLoaded", function () {

    const button = document.getElementById(
        "exploration-cooldown-button"
    );

    const secondsElement = document.getElementById(
        "exploration-cooldown-seconds"
    );

    if (!button || !secondsElement) {
        return;
    }

    let remaining = Number(
        button.dataset.remaining
    );

    const timer = setInterval(function () {

        remaining -= 1;

        if (remaining <= 0) {

            clearInterval(timer);

            window.location.reload();

            return;
        }

        secondsElement.textContent = remaining;

    }, 1000);

});