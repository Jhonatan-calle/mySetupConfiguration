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

local function set_hl(name, opts)
  vim.api.nvim_set_hl(0, name, opts)
end

vim.api.nvim_create_autocmd("ColorScheme", {
  callback = function()
    -- 1) Texto base más “fuerte”
    -- (ajusta si lo ves demasiado)
    set_hl("Normal", { fg = "#E6E6E6", bg = "NONE", bold = true })
    set_hl("NormalNC", { fg = "#E0E0E0", bg = "NONE", bold = true })

    -- 2) Comentarios: que no queden lavados
    set_hl("Comment", { fg = "#9AA5CE", italic = false, bold = true })

    -- 3) Números de línea más visibles
    set_hl("LineNr", { fg = "#8A93B5", bold = true })
    set_hl("CursorLineNr", { fg = "#FFFFFF", bold = true })

    -- 4) CursorLine / Visual con más contraste
    set_hl("CursorLine", { bg = "#2A2F45" })
    set_hl("Visual", { bg = "#3A4160" })

    -- 5) Separadores/ventanas más notables
    set_hl("WinSeparator", { fg = "#4C567A", bold = true })

    -- 6) Diagnósticos más legibles (opcional)
    set_hl("DiagnosticVirtualTextError", { bold = true })
    set_hl("DiagnosticVirtualTextWarn", { bold = true })
    set_hl("DiagnosticVirtualTextInfo", { bold = true })
    set_hl("DiagnosticVirtualTextHint", { bold = true })
  end,
})
