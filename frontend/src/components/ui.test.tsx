import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ConfirmDialog, LabeledSelect, OrderTransitionControls } from "./ui";

describe("UI foundations", () => {
  it("renders distinct select labels while emitting values", () => {
    const change = vi.fn();
    render(<LabeledSelect label="Branch" value="" onChange={change} options={[{ value: "branch-1", label: "North Campus" }]} />);
    expect(screen.getByText("North Campus")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Branch"), { target: { value: "branch-1" } });
    expect(change).toHaveBeenCalledWith("branch-1");
  });

  it("requires explicit confirmation", () => {
    const confirm = vi.fn();
    render(<ConfirmDialog open title="Delete address?" description="This cannot be undone." onCancel={() => undefined} onConfirm={confirm} />);
    expect(confirm).not.toHaveBeenCalled();
    fireEvent.click(screen.getByText("Confirm"));
    expect(confirm).toHaveBeenCalledOnce();
  });

  it("only offers legal order transitions", () => {
    render(<OrderTransitionControls status="PREPARING" onTransition={() => undefined} />);
    expect(screen.getByText("Mark ready")).toBeTruthy();
    expect(screen.queryByText("Mark completed")).toBeNull();
    expect(screen.queryByText("Cancel order")).toBeNull();
  });
});
