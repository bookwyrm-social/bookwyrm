/* exported XhrFiles */
/* globals BookWyrm */

let XhrFiles = new (class {
    constructor() {
        this.initEventListeners();
    }

    initEventListeners() {
        window.addEventListener("dragover", (e) => { e.preventDefault(); });

        window.addEventListener("drop", (e) => { e.preventDefault(); });

        document
            .querySelectorAll("[data-droppable-textfield]")
            .forEach((t) => t.addEventListener("drop", this.dropFile.bind(this)));
    }

    /**
     * Upload file when dropped in element
     *
     * @param  {Event} event
     * @return {undefined}
     */
    dropFile(event) {
        console.log(event);
        event.preventDefault();

        let result = "";
        // Use DataTransferItemList interface to access the file(s)
        [...event.dataTransfer.items].forEach((item, i) => {
            // If dropped items aren't files, reject them
            if (item.kind === "file") {
                const file = item.getAsFile();
                this.uploadFile(file);
                result += `• file[${i}].name = ${file.name}\n`;
            }
        });
        console.log(result);
    }

    uploadFile(file) {
        var xhr = new XMLHttpRequest();
        (xhr.upload || xhr).addEventListener('progress', function(e) {
            var done = e.position || e.loaded
            var total = e.totalSize || e.total;
            console.log('xhr progress: ' + Math.round(done/total*100) + '%');
        });
        xhr.addEventListener('load', function(e) {
            if (this.status != 200) {
                console.log(e);
                return;
            }
            console.log(e);
        });
        xhr.open('post', '/your-sever-url', true);
        var fd = new FormData();
        fd.append("filename", file.name);
        fd.append("file", file);
        xhr.send(fd);
    }
})();
