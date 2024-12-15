import Link from 'next/link';

export default function Home() {
  return (
    <div className= "container">
      <h1 className="title">DeFacto</h1>
      <p className='subtitle'>
        1. a legal concept used to refer to what happens in reality or in practice, as opposed
        to de jure (“from the law”), which refers to what is actually notated in legal code
      </p>

      <p className='subtitle'>
        2. A Large Language Model Agent capable of simulating court cases, analyzing legal documents, and preparing the
        next generation of attorneys.
      </p>

      {/* Mock Trial Simulation */}
      <div className= 'optionBox'>
        <h2>Mock Trial Simulation</h2>
        <p>Simulate Comprehensive Legal Scenarios with AI Agents</p>
        <Link href="/simulate">
          <button className='button'>Start</button>
        </Link>
      </div>

      {/* Legal Text Analysis */}
      <div className='optionBox'>
        <h2>Legal Text Analysis</h2>
        <p>Converse with the DeFacto Agent on Readings, Notes, etc.</p>
        <Link href="/analyze">
          <button className='button'>Start</button>
        </Link>
      </div>
    </div>
  );
}
