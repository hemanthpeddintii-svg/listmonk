import StepForm from "../../components/StepForm";
import { login } from "../actions";
export const metadata = { title: "Log in" };
export default function Login({ searchParams }) {
  return (<main className="wrap auth"><h1 className="vh">Log in</h1><span className="eyebrow"><i />Welcome back</span>
    <StepForm action={login} submit="Log in" hidden={{ next: searchParams?.next || "/dashboard" }} fields={[
      { name: "email", type: "email", label: "What's your email?", placeholder: "you@company.com", required: true, auto: "email", msg: "Enter your email." },
      { name: "password", type: "password", label: "And your password?", placeholder: "••••••••", required: true, auto: "current-password" }]} />
    {process.env.BILLING_MODE === "test" && <div className="testbox" style={{ display: "block" }}><b>Demo logins</b> (password <code>demo12345</code>)<br />
      admin@gccintel.test — admin · pro@gccintel.test — Pro · free@gccintel.test — Free</div>}
    <p className="mut">New here? <a href="/signup">Create a free account</a></p></main>);
}
