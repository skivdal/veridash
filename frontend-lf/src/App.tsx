import './App.css';
import { useAccount } from 'jazz-tools/react-core';
import { MyAppAccount, TodoItem } from './schema';
import { AuthStateIndicator } from './AuthStateIndicator';
import { useState } from 'react';

function App() {
  const [draft, setDraft] = useState("");

  const { me } = useAccount(MyAppAccount, {
    resolve: {
      profile: true,
      root: true,
    },
  });

  if (!me) {
    return <div>Loading...</div>;
  }

  return (
    <>
      <p>Hello, {me.profile.name}</p>

      <AuthStateIndicator />

      <ul>
        {me.root.todos?.map(item => {
          if (!item) return;
          return <li key={item.id}>{item.title} {item.completed ? "(completed)" : ""}</li>
        })}
      </ul>

      <input type="text" value={draft} onChange={(e) => setDraft(e.target.value)} />
      <button type="button" onClick={() => {
        if (!me.root || !me.root.todos) return;
        me.root.todos.push(TodoItem.create({ title: draft, completed: false }));
      }}>Add</button>
    </>
  );
}

export default App;

