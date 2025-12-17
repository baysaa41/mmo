// static/js/dropzone.init.js

// Disable auto attaching .dropzone elements
Dropzone.autoDiscover = false;


// ✅  Main Dropzone initializer
function initDropzone(selector, resultId, uploadUrl, refreshCallback) {

    const dz = new Dropzone(selector, {
        url: uploadUrl,
        method: "post",
        uploadMultiple: true,
        parallelUploads: 5,
        maxFilesize: 10,           // MB
        paramName: "file",
        headers: {
            "X-CSRFToken": getCookie("csrftoken"),
        },
        params: { result_id: resultId },
        addRemoveLinks: true,
        dictDefaultMessage: "📤 Энд зураг чирж тавина уу, эсвэл дарж сонгоно уу",
        dictRemoveFile: "Устгах",

        init: function () {

            this.on("successmultiple", (files, response) => {
                if (response.success) {
                    showToast("✅ Амжилттай илгээлээ!", "success");
                    if (refreshCallback) refreshCallback();
                } else {
                    showToast("⚠️ Зарим файл алдаатай", "warning");
                }
            });

            this.on("errormultiple", () => {
                showToast("❌ Файл илгээхэд алдаа гарлаа", "danger");
            });

            this.on("removedfile", (file) => {
                if (file.upload && file.upload.uuid && file.serverId) {
                    deleteUploaded(file.serverId, refreshCallback);
                }
            });
        },

        // ✅ Assign serverId for delete later
        success: function (file, response) {
            if (response.uploaded && response.uploaded.length > 0) {
                file.serverId = response.uploaded[0].id;
            }
        }

    });

    return dz;
}


// ✅ Delete uploaded image
function deleteUploaded(uploadId, refresh) {
    fetch(`/api/upload/delete/${uploadId}/`, {
        method: "DELETE",
        headers: { "X-CSRFToken": getCookie("csrftoken") }
    })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                showToast("🗑 Устгагдлаа", "info");
                if (refresh) refresh();
            }
        });
}


// ✅ Toast message helper
function showToast(message, type = "info") {
    const colors = {
        success: "#10b981",
        danger: "#ef4444",
        warning: "#f59e0b",
        info: "#3b82f6"
    };
    const toast = document.createElement("div");
    toast.style.cssText = `
        position: fixed; bottom: 20px; right: 20px;
        background: ${colors[type]}; color: white;
        padding: 12px 20px; border-radius: 6px; font-size: 0.9rem;
        box-shadow: 0 3px 10px rgba(0,0,0,0.2);
        z-index: 9999; opacity: 0; transition: opacity .3s;
    `;
    toast.innerText = message;
    document.body.appendChild(toast);
    // fade-in
    setTimeout(() => toast.style.opacity = 1, 50);
    // fade-out
    setTimeout(() => {
        toast.style.opacity = 0;
        setTimeout(() => toast.remove(), 400);
    }, 2500);
}


// ✅ CSRF helper
function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(";").shift();
}
