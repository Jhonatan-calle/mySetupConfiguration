-- Keymaps are automatically loaded on the VeryLazy event
-- Default keymaps that are always set: https://github.com/LazyVim/LazyVim/blob/main/lua/lazyvim/config/keymaps.lua
-- Add any additional keymaps here
--
--
-- Keymaps personalizados
local map = vim.keymap.set

-- Guardar con Ctrl+S
map("i", "<C-s>", "<Esc>:w<CR>", { desc = "Save and exit insert mode" })
map("n", "<C-s>", "<cmd>w<cr>", { desc = "Save file" })
map("v", "<C-s>", "<Esc>:w<CR>", { desc = "Save and exit visual mode" })
map("x", "<C-s>", "<Esc>:w<CR>", { desc = "Save and exit visual mode" })

