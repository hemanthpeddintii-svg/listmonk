import { ActionForm } from "../../components/Forms";
import { signup } from "../actions";
export const metadata = { title: "Sign up" };
export default function Signup() {
  return (<main><h1>Create your free account</h1>
    <ActionForm action={signup} submit="Sign up">
      <input name="name" placeholder="Name" />
      <input name="email" type="email" placeholder="Work email" required />
      <input name="password" type="password" placeholder="Password (8+ chars)" minLength={8} required />
    </ActionForm>
    <p className="mut">Already have an account? <a href="/login">Log in</a></p></main>);
}
