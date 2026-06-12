return {
  "lervag/vimtex",
  lazy = false,
  init = function()
    vim.g.vimtex_view_method = "zathura"
    vim.g.vimtex_view_forward_search_on_start = true
    vim.g.vimtex_tracking = false

    vim.g.vimtex_compiler_latexmk = {
      build_dir = "",
      callback = 1,
      continuous = 0,
      executable = "latexmk",
      options = {
        "-verbose",
        "-file-line-error",
        "-synctex=1",
        "-interaction=nonstopmode",
      },
    }
  end,
  config = function()
    local vimtex_group = vim.api.nvim_create_augroup("VimTeXTracking", { clear = true })

    vim.api.nvim_create_autocmd("User", {
      pattern = "VimtexEventCompileSuccess",
      group = vimtex_group,
      callback = function()
        vim.g.vimtex_tracking = true
      end,
    })

    vim.api.nvim_create_autocmd("CursorMoved", {
      group = vimtex_group,
      pattern = "*.tex",
      callback = function()
        if vim.fn.mode() == "n" and vim.g.vimtex_tracking then
          pcall(vim.cmd, "VimtexView")
        end
      end,
    })
  end,
}
