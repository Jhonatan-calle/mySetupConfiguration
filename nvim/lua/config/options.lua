-- Options are automatically loaded before lazy.nvim startup
-- Default options that are always set: https://github.com/LazyVim/LazyVim/blob/main/lua/lazyvim/config/options.lua
-- Add any additional options here
vim.opt.clipboard = "unnamedplus"
vim.opt.wrap = true
vim.g.autoformat = false
vim.opt.wrap = true
vim.opt.breakindent = true

-- If no prettier config file is found, the formatter will not be used
vim.g.lazyvim_prettier_needs_config = false

vim.opt.termguicolors = true
vim.opt.background = "light"
