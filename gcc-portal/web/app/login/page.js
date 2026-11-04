import { ActionForm } from "../../components/Forms";
import { login } from "../actions";
export const metadata = { title: "Log in" };
export default function Login({ searchParams }) {
  return (<main><h1>Log in</h1>
    <ActionForm action={login} submit="Log in">
      <input type="hidden" name="next" value={searchParams?.next || "/dashboard"} />
      <input name="email" type="email" placeholder="Email" required />
      <input name="password" type="password" placeholder="Password" required />
    </ActionForm>
    <p className="mut">New here? <a href="/signup">Create a free account</a></p></main>);
}
