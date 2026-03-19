-- Autocmds are automatically loaded on the VeryLazy event
-- Default autocmds that are always set: https://github.com/LazyVim/LazyVim/blob/main/lua/lazyvim/config/autocmds.lua
--
-- Add any additional autocmds here
-- with `vim.api.nvim_create_autocmd`
--
-- Or remove existing autocmds by their group name (which is prefixed with `lazyvim_` for the defaults)
-- e.g. vim.api.nvim_del_augroup_by_name("lazyvim_wrap_spell")
--
--
---- Autocmds are automatically loaded on the VeryLazy event
-- Add any additional autocmds here

-- nvim/lua/config/autocmds.lua

local function set_hl(name, opts)
  vim.api.nvim_set_hl(0, name, opts)
end

vim.api.nvim_create_autocmd("ColorScheme", {
  callback = function()
    local is_light = vim.o.background == "light"

    if is_light then
      -- Para modo claro, NO uses fg casi blanco
      set_hl("Normal", { fg = "#111111", bg = "#FFFFFF", bold = true })
      set_hl("NormalNC", { fg = "#111111", bg = "#FFFFFF", bold = true })
      set_hl("Comment", { fg = "#4B5563", italic = false, bold = true })
      set_hl("CursorLine", { bg = "#E5E7EB" })
      set_hl("Visual", { bg = "#CBD5E1" })
      set_hl("LineNr", { fg = "#6B7280", bold = true })
      set_hl("CursorLineNr", { fg = "#000000", bold = true })
      set_hl("WinSeparator", { fg = "#9CA3AF", bold = true })
    else
      set_hl("Normal", { fg = "#E6E6E6", bg = "NONE", bold = true })
      set_hl("NormalNC", { fg = "#E0E0E0", bg = "NONE", bold = true })
      set_hl("Comment", { fg = "#9AA5CE", italic = false, bold = true })
      set_hl("CursorLine", { bg = "#2A2F45" })
      set_hl("Visual", { bg = "#3A4160" })
      set_hl("LineNr", { fg = "#8A93B5", bold = true })
      set_hl("CursorLineNr", { fg = "#FFFFFF", bold = true })
      set_hl("WinSeparator", { fg = "#4C567A", bold = true })
    end
  end,
})
