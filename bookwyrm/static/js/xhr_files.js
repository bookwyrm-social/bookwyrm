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
        event.preventDefault();

        // Use DataTransferItemList interface to access the file(s)
        [...event.dataTransfer.items].forEach((item, i) => {
            // If dropped items aren't files, reject them
            if (item.kind === "file") {
                const file = item.getAsFile();
                this.uploadFile(file, event.target);
            }
        });
    }

    uploadFile(file, target) {
        const self = this;
        const xhr = new XMLHttpRequest();
        xhr.addEventListener('load', function(e) {
            if (this.status != 201) {
                console.log(e);
                return;
            }
            const responseJSON = JSON.parse(e.target.responseText);
            self.insertImageMarkdown(target, file, responseJSON);
        });
        xhr.open('post', '/upload', true);
        const fd = new FormData();
        fd.append("filename", file.name);
        fd.append("file", file);
        fd.append("csrfmiddlewaretoken", this.csrfToken());

        xhr.send(fd);
    }

    csrfToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]').value;
    }

    insertImageMarkdown(target, file, metadata) {
        const imageMarkdown = `!image(${metadata.name})`;
        const content = target.value;
        const caret = target.selectionEnd;
        const preCaret = content.slice(0, caret);
        const postCaret = content.slice(caret);
        target.value = preCaret.concat(imageMarkdown, postCaret);
    }
})();
