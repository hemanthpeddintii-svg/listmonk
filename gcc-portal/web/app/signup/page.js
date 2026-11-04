import StepForm from "../../components/StepForm";
import { signup } from "../actions";
export const metadata = { title: "Sign up" };
export default function Signup() {
  return (<main className="wrap auth"><span className="eyebrow"><i />Free forever plan</span>
    <StepForm action={signup} submit="Create account" fields={[
      { name: "name", label: "First, what should we call you?", placeholder: "Your name", auto: "name" },
      { name: "email", type: "email", label: "Your work email?", placeholder: "you@company.com", required: true, auto: "email", msg: "Enter a valid email." },
      { name: "password", type: "password", label: "Pick a password.", placeholder: "8+ characters", required: true, minLength: 8, auto: "new-password", msg: "At least 8 characters." }]} />
    <p className="mut">Already have an account? <a href="/login">Log in</a></p></main>);
}
