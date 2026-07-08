import { useState } from 'react';

function App() {
  const [enemyType, setEnemyType] = useState('regular_zombie');
  const [lines, setLines] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleGenerate = async () => {
    setLoading(true);
    setError(null);

    try {
      const res = await fetch('http://localhost:8000/graphql', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: `
            mutation GenerateBark($enemyType: String!) {
              generateBark(enemyType: $enemyType) {
                id
                enemyType
                lines
                createdAt
              }
            }
          `,
          variables: { enemyType },
        }),
      });

      const data = await res.json();

      if (data.errors) {
        throw new Error(data.errors[0].message);
      }

      setLines(data.data.generateBark.lines);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: '2rem', fontFamily: 'sans-serif', maxWidth: '500px' }}>
      <h1>Bark Generator</h1>

      <label>
        Enemy type:{' '}
        <input
          value={enemyType}
          onChange={(e) => setEnemyType(e.target.value)}
        />
      </label>

      <button onClick={handleGenerate} disabled={loading} style={{ marginLeft: '1rem' }}>
        {loading ? 'Generating...' : 'Generate Bark Lines'}
      </button>

      {error && <p style={{ color: 'red' }}>Error: {error}</p>}

      <ul>
        {lines.map((line, i) => (
          <li key={i}>{line}</li>
        ))}
      </ul>
    </div>
  );
}

export default App;