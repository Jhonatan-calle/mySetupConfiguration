return {
  "NeogitOrg/neogit",
  dependencies = {
    "nvim-lua/plenary.nvim",
    "sindrets/diffview.nvim",
  },
  keys = {
    { "<leader>gg", function() require("neogit").open({ kind = "split" }) end, desc = "Neogit (split)" },
    { "<leader>gG", function() require("neogit").open({ kind = "tab" }) end, desc = "Neogit (tab)" },
  },
  opts = {
    disable_signs = false,
    disable_context_highlighting = false,
    disable_commit_confirmation = false,
    remember_settings = true,
    integrations = { diffview = true },
  },
}
