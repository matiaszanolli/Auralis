import { describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";

import { render, screen } from "@/test/test-utils";
import { SearchInput } from "./SearchInput";

const renderInput = (onClear = vi.fn()) => {
  render(
    <SearchInput
      query="daft punk"
      loading={false}
      onQueryChange={vi.fn()}
      onClear={onClear}
    />,
  );
  return onClear;
};

describe("SearchInput clear button (#5127)", () => {
  it("has an accessible name when a query is present", () => {
    renderInput();

    expect(
      screen.getByRole("button", { name: /clear search/i }),
    ).toBeInTheDocument();
  });

  it("is reachable by Tab and activates with Enter, Space, and click", async () => {
    const user = userEvent.setup();
    const onClear = renderInput();
    const input = screen.getByPlaceholderText(/search/i);
    const clearButton = screen.getByRole("button", { name: /clear search/i });

    await user.tab();
    expect(input).toHaveFocus();
    await user.tab();
    expect(clearButton).toHaveFocus();

    await user.keyboard("{Enter}");
    await user.keyboard(" ");
    await user.click(clearButton);

    expect(onClear).toHaveBeenCalledTimes(3);
  });
});
