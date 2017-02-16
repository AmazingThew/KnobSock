using System;
using System.Net.Sockets;
using System.Threading;
using UnityEngine;
using System.Linq;

public class KnobComponent : MonoBehaviour
{
	const int _numKnobs = 24;
	float[] _knobs = new float[_numKnobs];

	void Start()
	{
		Knobs.Start(_numKnobs);
	}

	void Update()
	{
		for (int i = 0; i < _numKnobs; i++)
		{
			_knobs[i] = Knobs.Get(i);
			Shader.SetGlobalFloat("Knob" + i.ToString(), _knobs[i]);
		}
	}

	void OnDestroy()
	{
		print(String.Join("\n", Enumerable.Range(0, _numKnobs).Select(i => String.Format("{0}:\t{1}", i, Knobs.Get(i))).ToArray()));
		Knobs.Stop();
	}
}

public class Knobs
{
	static int _size;
	public static int[] knobs;

	static Socket _sock;

	static Thread _worker;
	static bool _running = false;

	public static void Start(int numKnobs)
	{
		if (!_running)
		{
			_size = numKnobs;
			knobs = new int[_size];

			try
			{
				_sock = new Socket(AddressFamily.InterNetwork, SocketType.Stream, ProtocolType.Tcp);
				_sock.Connect("localhost", 8008);

				_worker = new Thread(new ThreadStart(ReadFromServer));
				_worker.Start();

				_running = true;
			}
			catch (SocketException e)
			{
				Console.WriteLine(e);
			}
		}
	}

	public static void Stop()
	{
		if (_running)
		{
			_sock.Shutdown(SocketShutdown.Both);
			_sock.Close();
			_running = false;
		}
	}

	public static float Get(int index)
	{
		return Get(index, 0, 1);
	}

	public static float Get(int index, float max)
	{
		return Get(index, 0, max);
	}

	public static float Get(int index, float min, float max)
	{
		float value = (float)knobs[index] / 127.0f;
		return (1 - value) * min + value * max;
	}


	static void ReadFromServer()
	{
		byte[] sockBuffer = new byte[_size];

		try
		{
			while (_running)
			{
				if (_sock.Receive(sockBuffer, _size, SocketFlags.None) > 0)
				{
					for (int i = 0; i < _size; i++)
					{
						knobs[i] = sockBuffer[i];
					}
				}
				else
				{
					Console.WriteLine("Socket connection lost; aborting");
					_sock.Shutdown(SocketShutdown.Both);
					_sock.Close();
					break;
				}
			}
		}
		catch (SocketException e)
		{
			Console.WriteLine(e);
		}
	}
}
