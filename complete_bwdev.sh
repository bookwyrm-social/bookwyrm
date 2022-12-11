#/usr/bin/env bash
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
pytest_coverage_report
collectstatic
makemessages
compilemessages
update_locales
build
clean
black
prettier
eslint
stylelint
formatters
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
remove_2fa
confirm_email
runweb" -o bashdefault -o default bw-dev
