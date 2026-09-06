#
# ~/.bash_profile
#

[[ -f ~/.bashrc ]] && . ~/.bashrc

if [ "$(tty)" = "/dev/tty1" ]; then
  exec start-hyprland
fi

export KITTY_SHELL_INTEGRATION=disabled

export PATH="$HOME/Downloads/flutter/bin:$PATH"