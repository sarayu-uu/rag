import { getRoleDefinition, ROLE_KEYS } from "../../../lib/roles";

export default function EditorHome() {
  const role = getRoleDefinition(ROLE_KEYS.EDITOR);
  return (
    <section className="panel role-home">
      <h2>{role.label} Scope</h2>
      <p>{role.description}</p>
      <ul>
        {role.responsibilities.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </section>
  );
}

