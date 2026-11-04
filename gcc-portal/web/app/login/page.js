import StepForm from "../../components/StepForm";
import { login } from "../actions";
export const metadata = { title: "Log in" };
export default function Login({ searchParams }) {
  return (<main className="wrap auth"><span className="eyebrow"><i />Welcome back</span>
    <StepForm action={login} submit="Log in" hidden={{ next: searchParams?.next || "/dashboard" }} fields={[
      { name: "email", type: "email", label: "What's your email?", placeholder: "you@company.com", required: true, auto: "email", msg: "Enter your email." },
      { name: "password", type: "password", label: "And your password?", placeholder: "••••••••", required: true, auto: "current-password" }]} />
    <p className="mut">New here? <a href="/signup">Create a free account</a></p></main>);
}
