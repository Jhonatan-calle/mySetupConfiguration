return {
  "iamcco/markdown-preview.nvim",
  ft = { "markdown" },
  init = function()
    vim.cmd([[
      function! OpenPreview(url) abort
        call system('qutebrowser ' . a:url . ' &')
      endfunction
    ]])
    vim.g.mkdp_browserfunc = "OpenPreview"
  end,
  keys = {
    { "<leader>mp", ":MarkdownPreviewToggle<CR>", desc = "Toggle markdown preview" },
  },
  build = function()
    vim.fn["mkdp#util#install"]()
  end,
}
