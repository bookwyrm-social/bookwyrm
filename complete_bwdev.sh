#/usr/bin/env bash
# for zsh, run:
# autoload bashcompinit
# bashcompinit
complete -W "up
service_ports_web
initdb
resetdb
makemigrations
migrate
bash
shell
dbshell
restart_celery
pytest
collectstatic
makemessages
compilemessages
update_locales
build
clean
black
prettier
stylelint
formatters
compilescss
collectstatic_watch
populate_streams
populate_lists_streams
populate_suggestions
generate_thumbnails
generate_preview_images
copy_media_to_s3
set_cors_to_s3
setup
admin_code
runweb" -o bashdefault -o default bw-dev
