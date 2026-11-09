import SignInForm from "@/components/auth/SignInForm";
import { Metadata } from "next";

export const metadata: Metadata = {
  title: "Iniciar Sesión - CINCO SAS",
  description: "Portal de autenticación de CINCO SAS.",
};

export default function Login() {
  return <SignInForm />;
}
