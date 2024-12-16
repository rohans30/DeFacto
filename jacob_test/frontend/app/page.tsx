import Link from 'next/link';

export default function Home() {
  return (
    <div className='dynamic-background'>
    <div className= "container">
      <h1 className="title">DeFacto</h1>
      <p className='subtitle' id='defacto-description1'>
        1. a legal concept used to refer to what happens in reality or in practice, as opposed
        to de jure (“from the law”)
      </p>

      <p className='subtitle' id='defacto-description2'>
        2. A Multi Agent Application capable of simulating court cases, analyzing legal documents, and preparing the
        next generation of attorneys.
      </p>

      {/* Mock Trial Simulation */}
      <div className= 'optionBox'>
        <h2>Mock Trial Simulation</h2>
        <p>Simulate Comprehensive Legal Scenarios with AI Agents</p>
        <Link href="/simulate">
          <button className='home-start-button'>Start</button>
        </Link>
      </div>

      {/* Legal Text Analysis */}
      <div className='optionBox'>
        <h2>Legal Text Analysis</h2>
        <p>Converse with the DeFacto Agent on Readings, Notes, etc.</p>
        <Link href="/analyze">
          <button className='home-start-button'>Start</button>
        </Link>
      </div>
    </div>
    </div>
  );
}
