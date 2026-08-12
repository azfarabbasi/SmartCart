document.addEventListener('DOMContentLoaded', function () {
    const btn = document.getElementById('printSlipBtn');
    if (btn) {
        btn.addEventListener('click', function () {
            window.print();
        });
    }
});
