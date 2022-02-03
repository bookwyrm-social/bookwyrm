The font file itself is not included in the Git repository to avoid putting
large files in the repo history. The Docker image should download the correct
font into this folder automatically.

In case something goes wrong, the font used is the Variable OTC TTF, available
as of this writing from the Adobe Fonts GitHub repository:
https://github.com/adobe-fonts/source-han-sans/tree/release#user-content-variable-otcs

BookWyrm expects the file to be in this folder, named SourceHanSans-VF.ttf.ttc
