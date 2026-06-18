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

-- Mover líneas con ALT + J/K (Hyprland ya no los intercepta)
map("n", "<A-j>", "<cmd>move .+1<cr>==", { desc = "Move line down" })
map("n", "<A-k>", "<cmd>move .-2<cr>==", { desc = "Move line up" })
map("i", "<A-j>", "<esc><cmd>move .+1<cr>==gi", { desc = "Move line down" })
map("i", "<A-k>", "<esc><cmd>move .-2<cr>==gi", { desc = "Move line up" })
map("v", "<A-j>", "<cmd>'<,'>move '>+1<cr>gv=gv", { desc = "Move line down" })
map("v", "<A-k>", "<cmd>'<,'>move '<-2<cr>gv=gv", { desc = "Move line up" })

