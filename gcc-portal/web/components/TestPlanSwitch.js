import { testSetPlan } from "../app/actions";
export default function TestPlanSwitch({ current }) {
  if (process.env.BILLING_MODE !== "test") return null;
  return (<form action={testSetPlan} className="testbox"><b>TEST MODE · no payment</b>
    <span className="mut"> Switch your plan instantly:</span>
    {["free", "pro", "team"].map(p => <button key={p} name="plan" value={p} className={"chip" + (current === p ? " on" : "")}>{p}</button>)}</form>);
}
