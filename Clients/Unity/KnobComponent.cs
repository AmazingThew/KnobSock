using System;
using System.Net.Sockets;
using System.Threading;
using UnityEngine;
using System.Linq;

public class KnobComponent : MonoBehaviour {

    const int numKnobs = 24;
    float[] knobs = new float[numKnobs];

    void Start()
    {
        Knobs.start(numKnobs);
    }

    void Update()
    {
        for (int i = 0; i < numKnobs; i++)
        {
            knobs[i] = Knobs.get(i);
            Shader.SetGlobalFloat("Knob" + i.ToString(), knobs[i]);
        }
    }

    void OnDestroy()
    {
        print(String.Join("\n", Enumerable.Range(0, numKnobs).Select(i => String.Format("{0}:\t{1}", i, Knobs.get(i))).ToArray()));
        Knobs.stop();
    }
}





public class Knobs
{
    private static int size;
    public static int[] knobs;

    private static Socket sock;

    private static Thread worker;
    private static bool running = false;

    public static void start(int numKnobs)
    {
        if (!running)
        {
            size = numKnobs;
            knobs = new int[size];

            try
            {
                sock = new Socket(AddressFamily.InterNetwork, SocketType.Stream, ProtocolType.Tcp);
                sock.Connect("localhost", 8008);

                worker = new Thread(new ThreadStart(readFromServer));
                worker.Start();

                running = true;
            }
            catch (SocketException e)
            {
                Console.WriteLine(e);
            }
        }
    }

    public static void stop()
    {
        if (running)
        {
            sock.Shutdown(SocketShutdown.Both);
            sock.Close();
            running = false;
        }
    }

    public static float get(int index)
    {
        return get(index, 0, 1);
    }

    public static float get(int index, float max)
    {
        return get(index, 0, max);
    }

    public static float get(int index, float min, float max)
    {
        float value = (float)knobs[index] / 127.0f;
        return (1 - value) * min + value * max;
    }


    private static void readFromServer()
    {
        byte[] sockBuffer = new byte[size];

        try
        {
            while (running)
            {
                if (sock.Receive(sockBuffer, size, SocketFlags.None) > 0)
                {
                    for (int i = 0; i < size; i++)
                    {
                        knobs[i] = sockBuffer[i];
                    }
                }
                else
                {
                    Console.WriteLine("Socket connection lost; aborting");
                    sock.Shutdown(SocketShutdown.Both);
                    sock.Close();
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


