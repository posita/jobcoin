## Introduction

This implementation has suffered through several (in my opinion avoidable) points of
friction, and I hope my feedback (see [**Commentary**](#commentary) below) proves useful
to Gemini recruiting so that improvements can be made.

Reviewers are encouraged to explore this solution as follows:

```
$ git clone https://github.com/posita/jobcoin.git
…
$ cd jobcoin/python
$ # make your own virtual environment here
…
$ pip install -r requirements.txt
…
$ pytest -vv
…
```

The above _should_ work without error. Consider starting any exploration of the
implementation in [`jobcoin/jobcoin.py`](jobcoin.py) and
[`tests/test_jobcoin.py`](../tests/test_jobcoin.py) and moving outward from there. I
have explicitly _not_ provided a solution via the provided [`cli.py`](../cli.py)
skeleton for reasons that will hopefully become clearer below.

## Commentary

I received this challenge via a generic email from a recruiter after two half-hour
initial phone screens (one with the recruiter and another with a Gemini employee). The
email from the recruiter contained the following the instructions:

> Thanks so much for chatting with &lt;INTERVIEWER&gt; _[sic]_. They really enjoyed the
> opportunity to learn a bit more about you and your background.
>
> As a next step in the process, we'd love for you to give this code challenge a shot.
> The details of the exercise can be found
> [here](https://docs.google.com/document/d/1mlK67tEY7SvmtUDacVveJXufTWExwlQB3BPGTLyPkG0/edit?usp=sharing).
> The unique environment to your world for use is linked here _[sic; no link was
> provided]_
>
> We provide a few templates in a few different languages to get you started, but please
> pick the language you're most comfortable writing in!
>
> Let me know when you think you'll be able to tackle this so we can stay up to date on
> your timeline.
>
> If you run into any questions along the way, don't hesitate to reach out.

Almost immediately after digging in, I reached out to the recruiter with the following
questions over several emails:

1. The doc you sent does not (as far as I can tell) instruct me **_where_** to send my
   questions, only that I should send them. To whom should I be addressing these? To
   whom should I send a submission?

2. How much time am I expected to invest in this?

3. [I]t looks like I’m missing an instance-specific URL. … I am fine using that
   “todo_my_instance” URL, if that’s acceptable, but I wanted to make sure I wasn’t
   supposed to be hitting up something else?

4. The API docs allude to a “UI” used to create coins. From
   [this](https://jobcoin.gemini.com/todo_my_instance/api#transactions-transactions-get):

   > - Some transactions lack a “fromAddress” - those are ones where Jobcoins were created from the UI.

   Where is the aforementioned UI? It’s not at https://jobcoin.gemini.com/ or
   https://jobcoin.gemini.com/todo_my_instance/.

I also later tried the following (none of which worked):

- https://jobcoin.gemini.com/admin/
- https://jobcoin.gemini.com/ui/
- https://jobcoin.gemini.com/todo_my_instance/admin/
- https://jobcoin.gemini.com/todo_my_instance/ui/
- https://admin.jobcoin.gemini.com/
- https://ui.jobcoin.gemini.com/

I received the following as the sole response to my various questions:

> It shouldn’t take longer than a day or two tbh. Please feel free using whatever
> instance/tool/ language makes sense.

At least (in my case) the recruiter was correct in the time estimate. I probably spent
the better part of two days (around 6-7 hours in total) coding up what’s here (not
including this commentary).

The included instructions provide:

> We are primarily looking for you to demonstrate an understanding of the problem above
> and decompose it into a well structured solution … . We understand you have time
> constraints; feel free to cut yourself off before everything is complete, and document
> what your next steps would be in a README or comments.

As I attempt to explain herein, that is a substantial ask, no matter where one stops
coding. I would caution that such a time investment is not likely useful as a screening
exercise. At the very least, it probably tends to exclude the very candidates Gemini may
most benefit from. Experienced engineers, for example, tend to be those whose time is
pretty valuable. (Apparently, I am an exception. Or perhaps I am [motivated by something
else](https://www.goodreads.com/quotes/8701577-man-naturally-desires-not-only-to-be-loved-but-to).
I will leave that to the reader to ponder.)

A [“boilerplate” repo](https://github.com/gemini/jobcoin-boilerplate) is provided, but,
in my case, the Python version served more as a distraction than a boon. (I did not
examine the others.) I think the intention was to provide structured primitives and a
complimentary set of unit tests narrowing the implementer’s focus to more important
parts of the problem. In practice, however, I think this exercise would have taken me
less time had I started from scratch. The interactive command line interface was
confusing. The unit tests required a public internet connection to test, and assumed
full access to the server component, presumably including the ability to create coins
and facilitate transactions through some other interface, which I lacked.

In light of my inability to get timely clarity on questions or gain access to necessary
functionality, the work to complete this challenge in what I perceived to be a
minimally-tolerable way ballooned to the following:

1. Re-implement the entire server API to run locally. This was necessary to unlock the
   ability to create coins, since I lacked access to the necessary UI. (I tried working
   around this by `POST`ing a transaction without a `fromAddress` using the real API,
   but this was disallowed by the server.) Further, it afforded testing without
   requiring an internet connection, which seems to me a generally useful and important
   characteristic of any body of tests.

2. Replace `requests` with `aiohttp`, in part because `requests` is synchronous and in
   part because testing tends to be challenging and fragile. To the former point, a
   thing periodically polling an endpoint (as is the case with this API) is likely
   sleeping or I/O bound. Coupled with an interactive command line interface, that
   implies leaning heavily on something like threads, which are typically a centerpiece
   of a coding challenge, not merely a stepping stone. To the latter point, while any
   concurrency model presents its own testing challenges, the primary strategy with
   `requests` (as far as I am aware) is to
   [`patch`](https://docs.python.org/3/library/unittest.mock.html#unittest.mock.patch)
   and mock every response. I am not generally a fan of that approach.

   My testing strategy still suffers from some dysfunctions, however. Examples include,
   leaning on integration tests as a substitute for unit tests at higher levels and
   sleeping to advance logic. These can be corrected with design changes that I elected
   not to pursue in the interest of time. (As a side note, [Twisted has a very useful
   clock
   abstraction](https://twistedmatrix.com/documents/current/core/development/policy/test-standard.html#real-time)
   to address the latter issue. `asyncio` might have a similar mechanism, though I was
   unable to find one that suited my needs. Ref:
   [aio-libs/aiohttp#5834](https://github.com/aio-libs/aiohttp/issues/5834) and
   [“Mocking the Internal Clock of Asyncio Event
   Loop”](https://stackoverflow.com/questions/53829383/mocking-the-internal-clock-of-asyncio-event-loop/68152116#68152116).)

3. Replace most of the boilerplate and tests because they were tightly coupled to
   `requests` and to accessing the public API. Completely ignore [`cli.py`](../cli.py),
   since it was not easily salvageable in a world without some out-of-band way to drive
   coin creation and transfers. To be fair, solutions do exist (like leaning on the
   server replacement for testing to emulate behavior locally, and expanding user
   interactivity), but they would require substantial reworking that felt well beyond
   the scope of what was intended.

4. Build a rudimentary parsing and validation abstraction around the raw API. This was
   needed because the API returns JSON blobs whose values are _all_ strings.
   Semantically, those strings sometimes contain dates and floating point numbers. This
   presents some subtle complications that the presenters likely left as sub-exercises
   of the challenge.

   - First, let’s tackle the easier of the two: dates. I suppose these could have been
     ignored, but, in my case, I wanted my mixer to afford time to accumulate deposits
     before it engaged in a payout. This meant keeping track of transaction times, which
     meant date parsing. Going back-and-forth from an ISO-formatted string to a native,
     timezone aware object isn’t _hard_ (most languages have decent library support for
     this), but it’s not trivial either. There are sharp edges that are likely only
     easily avoided with experience.

   - Second, let’s address floating point numbers. We’re dealing with arbitrary amounts
     in the network transactions. The nature of the problem means some version of
     division at some point. This means we have to be conscious about avoiding repeating
     decimals and lossy operations _everywhere_. We also care about lossless conversion
     back into strings (because that’s what the API requires).

   That’s _already_ a lot to keep track of, despite being a small part of an interview
   exercise. A real version of an API client abstraction would likely have substantial
   validation and signals (e.g., a useful exception hierarchy) to surface problems to
   native callers in useful ways. In the interest of time, I chose to largely gloss over
   failure detection and recovery. Nearly all errors in my implementation are fatal.

5. Implement the “mixer” in two parts: a “gatherer” to monitor each receiving address
   and move funds to a house address; and a “disburser” to monitor the house address and
   (after some delay) split and move funds to withdrawal addresses. This is also a
   problem with many toy subtleties and even more real world ones. The following should
   not be considered exhaustive.

   - One such subtlety is that the network itself does not (and likely cannot or at
     least should not) contain sufficient information to map receiving addresses to
     withdrawal addresses. That state must be kept (and shared within the application)
     outside the transaction network. In the real world, to be robust to failures, this
     means reliably persisted extra-network state. In the interest of time, I did not
     introduce persistent storage.

   - Another subtle aspect that _does_ come into play is timing. For a mixer to have any
     value, it cannot disburse funds immediately after receiving them. Otherwise, the
     likely result is that disbursements close-in-time involve _only_ a single set of
     withdrawal addresses, which defeats the goal of obscuring traceability.

   - Yet another subtlety involves validation of the map of receiving addresses to
     withdrawal addresses. Problems arise when a withdrawal address is shared among
     receiving addresses. My implementation detects this, but treats it as a fatal
     error. A more robust solution might be to provide a registration API that checked
     for prior use and rejected any attempt by a client to reuse a withdrawal address. I
     suspect this is the role the [`cli.py`](../cli.py) boilerplate was intended to
     play, but this was far from clear.

   - Yet another subtlety involves determining the amounts that should be sent to each
     withdrawal address. My implementation merely divides un-disbursed deposits equally
     among their corresponding withdrawal addresses, but where the received amounts and
     number of withdrawal addresses differ among receiving address (something likely to
     be the case in nearly all real world uses), that can ease reconstruction of
     transaction chains to identify funding sources, again defeating the goal of
     obscuring traceability. Meaningfully addressing this problem is far from trivial
     and likely requires great care.

   - Yet another subtlety is that transactions can occur at any time. Nothing prevents a
     party from sending additional funds to a receiving address long after a prior
     distribution. That implies that, without some additional mechanism or restrictions,
     once a receiving address is deployed, it must be monitored indefinitely. Mapped to
     a toy implementation, this means a certain amount of accounting and validation such
     that the ”disburser” may properly deal with transfers from receiving addresses
     after already disbursing prior transfers. (I have a test case that covers aspects
     of this.)

The instructions even identify some of these, explicitly. For example:

> Then, over some time the mixer will use the house account to dole out your bitcoin in
> smaller discrete increments to the withdrawal addresses that you provided, possibly
> after deducting a fee.

It’s not clear whether that’s intended as a description of a real world mixer, or
whether such behavior should be implemented as part of this exercise. (Obviously, my
attempt falls short on several fronts, including fee collection.)

Any _one_ (maybe two) of the aforementioned sub-problems is likely worthy of some
exploration in a single coding interview. In aggregate, this problem space feels more
appropriate to explore at a higher level (e.g., in an architectural interview). But
asking candidates to code a solution to a problem with this many subtleties and
complexities is not only irregular, it’s not clear what signal this question will to
surface in the real world.

When sufficiently defined and kept within a reasonable scope, take-home exercises can be
useful tools, both for screening and for pitching an opportunity. They can provide
valuable (but sadly often squandered) opportunities to boost recruiting efforts by
signaling company values as well as surfacing quality candidates that may otherwise be
excluded by traditional coding interviews (e.g., due to performance anxiety).

However, even when things go entirely as planned, _this_ problem likely excludes a lot
of valuable candidates. Add in the friction associated with a lack of communication,
faulty instructions, inadequate support, a distracting boilerplate, with no clear avenue
to gather needed assistance, I would not be surprised to learn that candidates
(especially high quality candidates) either tend to push back on this requirement, or
silently quit the process altogether. My hunch is that very few submissions are ever
made, and that a majority of those end up being woefully inadequate. If this is
something observable within your recruiting efforts, my humble advice is to consider
investing more time in a smaller and more polished take-home exercise:

- Consider providing a client library that handles data marshaling, etc., and a server
  implementation that runs locally, then let the candidate focus exclusively on the
  mixer. Asking the candidate to write both a reasonable client _and_ design and
  implement (or meaningfully describe) a reasonable mixer feels like a lot.

- Perhaps in deference to [RFC
  1925](https://datatracker.ietf.org/doc/html/rfc1925#section-2), unless you’re testing
  a candidate’s ability to investigate and fix bugs in complete isolation (which should
  probably be a separate exercise), whatever is presented to the candidate _has to
  work_. Requiring a candidate to implement a marshaling client, design and implement a
  mixer, _and_ discover and work around missing parts without assistance is excessive.
  _Inviting and competently responding to questions is a core feature of this
  ~~product~~ __problem__ in its current form._ Failing to deliver that feature makes
  this ~~product unusable~~ __problem excessively onerous__.

  It is often better to put _nothing_ in front of a ~~customer~~ __candidate__, than
  something that promises essential functionality it does not provide.

- Seek an exercise where candidates can stop at any time without loss of signal. Coding
  a partial solution, then writing documentation describing code not yet written will
  probably take more time than merely coding the entire thing. Despite good intentions,
  the provided advice probably does not meaningfully address a candidate’s need to limit
  involvement. Instead, consider problems that naturally lend themselves to incremental
  progress such that one can still get a fair idea of a candidate’s capabilities no
  matter where that person stops.

At this point, designers of this problem may be saying, “But Matt! That means we’d have
to build versions of that for every language! A core design principle of this exercise
is the ability allow the candidate to work using whatever tools they desire! Allowing
(and role modeling) tests that run against a server sitting on the public internet is a
conscious compromise designed to avoid some of the problems you’re talking about. We
want them to think about the mixer, so we tried making everything else as easy as we
could while still allowing candidates flexibility on tooling choice.” They’d be
absolutely right, in the sense that providing client implementations in Go, Node,
Python, and Scala puts a candidate who wants to use C++ or Rust at a substantial
disadvantage.

I think letting candidates use familiar tools in a take-home exercise is a worthy
priority. My humble observation is that this problem is ill-suited for that. Coupling
that kind of freedom with a problem of this complexity means a lot of work for
_someone_. Better options for free form submissions might tackle narrower slices of
this. For example: “Jobcoin is easier than Bitcoin! Here’s a simple API for
transactions. Build a validating client in your favorite language.”

That alone could provide useful signal, but it could also provide expansion
opportunities for subsequent “onsite” interviews:

- “You rocked the take-home! Now let’s expand on that together to build an address
monitor that keeps track of the aggregate balance across several addresses;” or

- “Now let’s work on some wallet functionality. Bob wants to pay Alice 50 Jobcoin. He
owns three separate addresses, each with 20 Jobcoin. Build a function that, given a set
of source addresses (the wallet), an aggregate amount, and a destination address,
returns a set of transactions necessary to effect the transfer,” etc.

If you’re dead set on using the mixer as an interview problem, consider trying to
eliminate _all_ distractions (the client, the API, the concurrency, floating point math,
etc.) and laser focus on the important bit. For example: “In any language you want,
write a mixer distribution _function_. It should take [describe some data structure
mapping receiving addresses to amounts owed and destination addresses] and return a set
of [describe some transaction data structure] records that describe the payouts.” You
can always quiz candidates about the things you eliminated in the exercise as follow-up
questions.

I hope this feedback is useful to you. Feel free to ignore or reject it without fear of
judgment or reprisal. In any event, I appreciate your time and attention.
