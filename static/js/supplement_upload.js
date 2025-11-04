/**
 * Supplement & Exam upload handler
 * Works for BOTH: statically rendered AND AJAX-loaded forms
 * Auto-detects every form whose id starts with "upload-form-"
 * Sends fetch() with X-Requested-With header
 * Handles success + failed files + UI update
 * DEBUG logs included
 */

(function () {
    console.log("✅ supplement_upload.js loaded");

    // Event delegation — works even if forms appear later via AJAX
    document.addEventListener("submit", function (e) {
        const form = e.target;
        if (!form.id || !form.id.startsWith("upload-form-")) return; // not our form
        e.preventDefault();

        console.log("📌 AJAX Upload Intercepted:", form.id);

        const formData = new FormData(form);
        const resultId = form.id.replace("upload-form-", "");
        const resultsDiv = document.getElementById("upload-results-" + resultId);
        const submitBtn = form.querySelector(".upload-submit-btn");
        const fileInput = form.querySelector('input[type="file"]');

        if (!fileInput || !fileInput.files.length) {
            alert("⚠️ Зураг сонгоно уу.");
            return;
        }

        submitBtn.disabled = true;
        submitBtn.innerText = "⏳ Хуулж байна...";
        resultsDiv.style.display = "block";
        resultsDiv.innerHTML = `<p style="color:gray;">⏳ Файл хуулж байна...</p>`;

        fetch(form.action, {
            method: "POST",
            body: formData,
            headers: new Headers({
                "X-Requested-With": "XMLHttpRequest"
            })
        })
            .then(res => res.json().then(data => ({ status: res.status, data })))
            .then(resp => {
                const data = resp.data;
                console.log("📥 SERVER RESPONSE >>>", data);

                submitBtn.disabled = false;
                submitBtn.innerText = "✅ Серверт хуулах";
                fileInput.value = "";

                resultsDiv.innerHTML = buildResultHTML(data);

                // Auto-update thumbnail list if available
                if (data.success && typeof window.refreshUploadedList === "function") {
                    window.refreshUploadedList(parseInt(resultId), data.uploaded_files);
                }
            })
            .catch(err => {
                console.error("❌ FETCH ERROR:", err);
                resultsDiv.innerHTML = `<div style="color:red;">❌ Алдаа гарлаа: ${err}</div>`;
                submitBtn.disabled = false;
                submitBtn.innerText = "✅ Серверт хуулах";
            });
    });

    function buildResultHTML(data) {
        let html = "";

        if (data.uploaded_files?.length) {
            html += `<div><strong style="color:#10b981;">✅ Амжилттай:</strong>`;
            data.uploaded_files.forEach(f => {
                html += `<div class="upload-result-item upload-result-success">📄 ${f.name}</div>`;
            });
            html += "</div>";
        }

        if (data.failed_files?.length) {
            html += `<div style="margin-top:.5rem;"><strong style="color:#ef4444;">❌ Амжилтгүй:</strong>`;
            data.failed_files.forEach(f => {
                html += `<div class="upload-result-item upload-result-error">📄 ${f.name}<br><small>${f.reason}</small></div>`;
            });
            html += "</div>";
        }

        html += `<p style="margin-top:1rem; font-weight:bold;">${data.message}</p>`;
        return html;
    }
})();
