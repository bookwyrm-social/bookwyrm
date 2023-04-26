# bw-dev auto-completions for fish-shell.
# copy this to ~/.config/fish/completions/ with the name `bw-dev.fish`
# this will only work if renamed to `bw-dev.fish`.

set -l commands up \
service_ports_web \
initdb \
resetdb \
makemigrations \
migrate \
bash \
shell \
dbshell \
restart_celery \
pytest \
pytest_coverage_report \
compile_themes \
collectstatic \
makemessages \
compilemessages \
update_locales \
build \
clean \
black \
prettier \
eslint \
stylelint \
formatters \
collectstatic_watch \
populate_streams \
populate_lists_streams \
populate_suggestions \
generate_thumbnails \
generate_preview_images \
remove_remote_user_preview_images \
copy_media_to_s3 \
set_cors_to_s3 \
setup \
admin_code \
remove_2fa \
confirm_email \
runweb

function __bw_complete -a cmds cmd desc
    complete -f -c bw-dev -n "not __fish_seen_subcommand_from $cmds" -a $cmd -d $desc
end

__bw_complete "$commands" "up"                                "bring one or all service(s) up"
__bw_complete "$commands" "service_ports_web"                 "run command on the web container with its portsenabled and mapped"
__bw_complete "$commands" "initdb"                            "initialize database"
__bw_complete "$commands" "resetdb"                           "!! WARNING !! reset database"
__bw_complete "$commands" "makemigrations"                    "create new migrations"
__bw_complete "$commands" "migrate"                           "perform all migrations"
__bw_complete "$commands" "bash"                              "open up bash within the web container"
__bw_complete "$commands" "shell"                             "open the Python shell within the web container"
__bw_complete "$commands" "dbshell"                           "open the database shell within the web container"
__bw_complete "$commands" "restart_celery"                    "restart the celery container"
__bw_complete "$commands" "pytest"                            "run unit tests"
__bw_complete "$commands" "compile_themes"                    "compile themes css files"
__bw_complete "$commands" "collectstatic"                     "copy changed static files into the installation"
__bw_complete "$commands" "makemessages"                      "extract all localizable messages from the code"
__bw_complete "$commands" "compilemessages"                   "compile .po localization files to .mo"
__bw_complete "$commands" "update_locales"                    "run makemessages and compilemessages for the en_US and additional locales"
__bw_complete "$commands" "build"                             "build the containers"
__bw_complete "$commands" "clean"                             "bring the cluster down and remove all containers"
__bw_complete "$commands" "black"                             "run Python code formatting tool"
__bw_complete "$commands" "prettier"                          "run JavaScript code formatting tool"
__bw_complete "$commands" "eslint"                            "run JavaScript linting tool"
__bw_complete "$commands" "stylelint"                         "run SCSS linting tool"
__bw_complete "$commands" "formatters"                        "run multiple formatter tools"
__bw_complete "$commands" "populate_streams"                  "populate the main streams"
__bw_complete "$commands" "populate_lists_streams"            "populate streams for book lists"
__bw_complete "$commands" "populate_suggestions"              "populate book suggestions"
__bw_complete "$commands" "generate_thumbnails"               "generate book thumbnails"
__bw_complete "$commands" "generate_preview_images"           "generate site/book/user preview images"
__bw_complete "$commands" "remove_remote_user_preview_images" "remove preview images for remote users"
__bw_complete "$commands" "collectstatic_watch"               "watch filesystem and copy changed static files"
__bw_complete "$commands" "copy_media_to_s3"                  "run the `s3 cp` command to copy media to a bucket on S3"
__bw_complete "$commands" "sync_media_to_s3"                  "run the `s3 sync` command to sync media with a bucket on S3"
__bw_complete "$commands" "set_cors_to_s3"                    "push a CORS configuration defined in .json to s3"
__bw_complete "$commands" "setup"                             "perform first-time setup"
__bw_complete "$commands" "admin_code"                        "get the admin code"
__bw_complete "$commands" "remove_2fa"                        "remove 2FA from user"
__bw_complete "$commands" "confirm_email"                     "manually confirm email of user and set active"
__bw_complete "$commands" "runweb"                            "run a command on the web container"


function __bw_complete_subcommand -a cmd
	complete -f -c bw-dev -n "__fish_seen_subcommand_from $cmd" $argv[2..-1]
end

__bw_complete_subcommand "up" -a "(docker-compose config --service)"
__bw_complete_subcommand "pytest" -a "bookwyrm/tests/**.py"
__bw_complete_subcommand "populate_streams" -a "--stream=" -d "pick a single stream to populate"
__bw_complete_subcommand "populate_streams" -l stream -a "home local books"
__bw_complete_subcommand "generate_preview_images" -a "--all"\
	-d "Generates images for ALL types: site, users and books. Can use a lot of computing power."
__bw_complete_subcommand "set_cors_to_s3" -a "**.json"
